import sqlalchemy as sa


def parse_path(type_, path):
    path = path.split('.')
    res = [(type_, path.pop(0))]
    while path:
        res.append((path.pop(0), path.pop(0)))
    return res

def format_path(path, head=False, tail=True):

    if len(path) == 1:
        if head and tail:
            return '%s.%s' % path[0]
        elif head:
            return path[0][0]
        elif tail:
            return path[0][1]
        else:
            raise ValueError('need head or tail when single-element path')

    parts = []
    parts.append(('%s.%s' % path[0]) if head else path[0][1])
    if len(path) > 1:
        parts.extend('%s.%s' % x for x in path[1:-1])
        parts.append(('%s.%s' % path[-1]) if tail else path[-1][0])
    return '.'.join(parts)


class ReadRequest(object):

    def __init__(self, request):

        self.request = request
        self.entity_type_name = request['type']
        self.filters = request['filters']
        self.return_fields = request['return_fields']
        self.limit = request['paging']['entities_per_page']
        self.offset = self.limit * (request['paging']['current_page'] - 1)

        self.aliased = set()
        self.aliases = {}

        self.joined = set()
        self.select_fields = []
        self.select_from = None
        self.where_clauses = []

        self.select_state = []

    def parse_path(self, path):
        return parse_path(self.entity_type_name, path)

    def get_entity(self, path):
        type_ = self.schema[path[-1][0]]
        return type_

    def get_field(self, path):
        type_ = self.schema[path[-1][0]]
        field = type_.fields[path[-1][1]]
        return field

    def get_table(self, path):
        name = format_path(path, head=True, tail=False)
        if name not in self.aliases:
            # we can return the real table the first path it is used from,
            # but after that we must alias it
            table = self.get_entity(path).table
            if table.name in self.aliased:
                table = table.alias(name)
            self.aliased.add(table.name)
            self.aliases[name] = table
        return self.aliases[name]

    def join(self, table, on):
        if table.name not in self.joined:
            self.select_from = self.select_from.outerjoin(table, on)
            self.joined.add(table.name)

    def prepare_joins(self, path):
        for i in xrange(0, len(path) - 1):
            field_path = path[:i+1]
            field = self.get_field(field_path)
            field.prepare_join(self, field_path, path[:i+2])

    def prepare_filters(self, filters):

        clauses = []
        for filter_ in filters['conditions']:

            if 'conditions' in filter_:
                clause = self.prepare_filters(filter_)
            else:

                raw_path = filter_['path']
                relation = filter_['relation']
                values = filter_['values']

                path = self.parse_path(raw_path)
                self.prepare_joins(path) # make sure it is availible

                field = self.get_field(path)
                clause = field.prepare_filter(self, path, relation, values)

            if clause is not None:
                clauses.append(clause)

        if clauses:
            return (sa.and_ if filters['logical_operator'] == 'and' else sa.or_)(*clauses)


    def prepare(self):

        self.select_from = self.get_table([(self.entity_type_name, None)])

        self.return_fields.append('id')
        
        for raw_path in self.return_fields:

            path = self.parse_path(raw_path)
            self.prepare_joins(path) # make sure it is availible

            field = self.get_field(path)
            state = field.prepare_select(self, path)

            self.select_state.append((path, field, state))

        clause = self.prepare_filters(self.filters)
        if clause is not None:
            self.where_clauses.append(clause)

        query = sa.select(self.select_fields).select_from(self.select_from)

        if self.where_clauses:
            query = query.where(sa.and_(*self.where_clauses))
        if self.offset:
            query = query.offset(self.offset)
        if self.limit:
            query = query.limit(self.limit)
        
        return query

    def extract(self, res):
        rows = []
        for i, raw_row in enumerate(res):
            row = {'type': self.entity_type_name}
            for path, field, state in self.select_state:
                try:
                    value = field.extract_select(self, path, state, raw_row)
                except KeyError:
                    pass
                else:
                    row[format_path(path, head=False)] = value
            rows.append(row)
        return rows

    def __call__(self, schema):

        self.schema = schema
        self.entity_type = schema[self.entity_type_name]

        query = self.prepare()
        res = schema.db.execute(query)

        return self.extract(res)
