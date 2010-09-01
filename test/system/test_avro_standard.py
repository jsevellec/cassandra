
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from . import AvroTester
import avro_utils
from avro.ipc import AvroRemoteException

class TestStandardOperations(AvroTester):
    """
    Operations on Standard column families
    """
    def test_insert_simple(self):       # Also tests get
        "setting and getting a simple column"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        params = dict()
        params['key'] = 'key1'
        params['column_parent'] = {'column_family': 'Standard1'}
        params['column'] = new_column(1)
        params['consistency_level'] = 'ONE'
        self.client.request('insert', params)

        read_params = dict()
        read_params['key'] = params['key']
        read_params['column_path'] = dict()
        read_params['column_path']['column_family'] = 'Standard1'
        read_params['column_path']['column'] = params['column']['name']
        read_params['consistency_level'] = 'ONE'

        cosc = self.client.request('get', read_params)

        assert_cosc(cosc)
        assert_columns_match(cosc['column'], params['column'])

    def test_remove_simple(self):
        "removing a simple column"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        params = dict()
        params['key'] = 'key1'
        params['column_parent'] = {'column_family': 'Standard1'}
        params['column'] = new_column(1)
        params['consistency_level'] = 'ONE'
        self.client.request('insert', params)

        read_params = dict()
        read_params['key'] = params['key']
        read_params['column_path'] = dict()
        read_params['column_path']['column_family'] = 'Standard1'
        read_params['column_path']['column'] = params['column']['name']
        read_params['consistency_level'] = 'ONE'

        cosc = self.client.request('get', read_params)

        assert_cosc(cosc)

        remove_params = read_params
        remove_params['clock'] = {'timestamp': timestamp()}

        self.client.request('remove', remove_params)

        avro_utils.assert_raises(AvroRemoteException,
                self.client.request, 'get', read_params)

    def test_batch_mutate(self):
        "batching addition/removal mutations"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        mutations = list()
       
        # New column mutations
        for i in range(3):
            cosc = {'column': new_column(i)}
            mutation = {'column_or_supercolumn': cosc}
            mutations.append(mutation)

        map_entry = {'key': 'key1', 'mutations': {'Standard1': mutations}}

        params = dict()
        params['mutation_map'] = [map_entry]
        params['consistency_level'] = 'ONE'

        self.client.request('batch_mutate', params)

        # Verify that new columns were added
        for i in range(3):
            column = new_column(i)
            cosc = self.__get('key1', 'Standard1', None, column['name'])
            assert_cosc(cosc)
            assert_columns_match(cosc['column'], column)

        # Add one more column; remove one column
        extra_column = new_column(3); remove_column = new_column(0)
        mutations = [{'column_or_supercolumn': {'column': extra_column}}]
        deletion = dict()
        deletion['clock'] = {'timestamp': timestamp()}
        deletion['predicate'] = {'column_names': [remove_column['name']]}
        mutations.append({'deletion': deletion})

        map_entry = {'key': 'key1', 'mutations': {'Standard1': mutations}}

        params = dict()
        params['mutation_map'] = [map_entry]
        params['consistency_level'] = 'ONE'

        self.client.request('batch_mutate', params)

        # Ensure successful column removal
        avro_utils.assert_raises(AvroRemoteException,
                self.__get, 'key1', 'Standard1', None, remove_column['name'])

        # Ensure successful column addition
        cosc = self.__get('key1', 'Standard1', None, extra_column['name'])
        assert_cosc(cosc)
        assert_columns_match(cosc['column'], extra_column)

    def test_get_slice_simple(self):
        "performing a slice of simple columns"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        columns = list(); mutations = list()

        for i in range(6):
            columns.append(new_column(i))

        for column in columns:
            mutation = {'column_or_supercolumn': {'column': column}}
            mutations.append(mutation)

        mutation_params = dict()
        map_entry = {'key': 'key1', 'mutations': {'Standard1': mutations}}
        mutation_params['mutation_map'] = [map_entry]
        mutation_params['consistency_level'] = 'ONE'

        self.client.request('batch_mutate', mutation_params)

        # Slicing on list of column names
        slice_params= dict()
        slice_params['key'] = 'key1'
        slice_params['column_parent'] = {'column_family': 'Standard1'}
        slice_params['predicate'] = {'column_names': list()}
        slice_params['predicate']['column_names'].append(columns[0]['name'])
        slice_params['predicate']['column_names'].append(columns[4]['name'])
        slice_params['consistency_level'] = 'ONE'

        coscs = self.client.request('get_slice', slice_params)

        for cosc in coscs: assert_cosc(cosc)
        assert_columns_match(coscs[0]['column'], columns[0])
        assert_columns_match(coscs[1]['column'], columns[4])

        # Slicing on a range of column names
        slice_range = dict()
        slice_range['start'] = columns[2]['name']
        slice_range['finish'] = columns[5]['name']
        slice_range['reversed'] = False
        slice_range['count'] = 1000
        slice_params['predicate'] = {'slice_range': slice_range}

        coscs = self.client.request('get_slice', slice_params)

        for cosc in coscs: assert_cosc(cosc)
        assert len(coscs) == 4, "expected 4 results, got %d" % len(coscs)
        assert_columns_match(coscs[0]['column'], columns[2])
        assert_columns_match(coscs[3]['column'], columns[5])

    def test_multiget_slice_simple(self):
        "performing a slice of simple columns, multiple keys"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        columns = list(); mutation_params = dict()

        for i in range(12):
            columns.append(new_column(i))

        # key1, first 6 columns
        mutations_one = list()
        for column in columns[:6]:
            mutation = {'column_or_supercolumn': {'column': column}}
            mutations_one.append(mutation)

        map_entry = {'key': 'key1', 'mutations': {'Standard1': mutations_one}}
        mutation_params['mutation_map'] = [map_entry]

        # key2, last 6 columns
        mutations_two = list()
        for column in columns[6:]:
            mutation = {'column_or_supercolumn': {'column': column}}
            mutations_two.append(mutation)

        map_entry = {'key': 'key2', 'mutations': {'Standard1': mutations_two}}
        mutation_params['mutation_map'].append(map_entry)

        mutation_params['consistency_level'] = 'ONE'

        self.client.request('batch_mutate', mutation_params)

        # Slice all 6 columns on both keys
        slice_params= dict()
        slice_params['keys'] = ['key1', 'key2']
        slice_params['column_parent'] = {'column_family': 'Standard1'}
        sr = {'start': '', 'finish': '', 'reversed': False, 'count': 1000}
        slice_params['predicate'] = {'slice_range': sr}
        slice_params['consistency_level'] = 'ONE'

        coscs_map = self.client.request('multiget_slice', slice_params)
        for entry in coscs_map:
            assert(entry['key'] in ['key1', 'key2']), \
                    "expected one of [key1, key2]; got %s" % entry['key']
            assert(len(entry['columns']) == 6), \
                    "expected 6 results, got %d" % len(entry['columns'])

    def test_get_count(self):
        "counting columns"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        mutations = list()

        for i in range(10):
            mutation = {'column_or_supercolumn': {'column': new_column(i)}}
            mutations.append(mutation)

        mutation_params = dict()
        map_entry = {'key': 'key1', 'mutations': {'Standard1': mutations}}
        mutation_params['mutation_map'] = [map_entry]
        mutation_params['consistency_level'] = 'ONE'

        self.client.request('batch_mutate', mutation_params)

        count_params = dict()
        count_params['key'] = 'key1'
        count_params['column_parent'] = {'column_family': 'Standard1'}
        sr = {'start': '', 'finish': '', 'reversed': False, 'count': 1000}
        count_params['predicate'] = {'slice_range': sr}
        count_params['consistency_level'] = 'ONE'

        num_columns = self.client.request('get_count', count_params)
        assert(num_columns == 10), "expected 10 results, got %d" % num_columns

    def test_multiget_count(self):
        "obtaining the column count for multiple rows"
        self.client.request('set_keyspace', {'keyspace': keyspace_name})

        mutations = list()

        for i in range(10):
            mutation = {'column_or_supercolumn': {'column': new_column(i)}}
            mutations.append(mutation)

        mutation_params = dict()
        mutation_params['mutation_map'] = list()
        for i in range(3):
            entry = {'key': 'k'+str(i), 'mutations': {'Standard1': mutations}}
            mutation_params['mutation_map'].append(entry)
        mutation_params['consistency_level'] = 'ONE'

        self.client.request('batch_mutate', mutation_params)

        count_params = dict()
        count_params['keys'] = ['k0', 'k1', 'k2']
        count_params['column_parent'] = {'column_family': 'Standard1'}
        sr = {'start': '', 'finish': '', 'reversed': False, 'count': 1000}
        count_params['predicate'] = {'slice_range': sr}
        count_params['consistency_level'] = 'ONE'

        counts = self.client.request('multiget_count', count_params)
        for e in counts:
            assert(e['count'] == 10), \
                "expected 10 results for %s, got %d" % (e['key'], e['count'])
