# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import time

import pytest

from replication_handler.testing_helper.util import execute_query_get_one_row
from replication_handler.testing_helper.util import RBR_SOURCE
from replication_handler.testing_helper.util import SCHEMA_TRACKER
from replication_handler.testing_helper.util import set_heartbeat


@pytest.mark.itest
class TestEndToEnd(object):

    @pytest.fixture
    def table_name(self):
        return 'biz'

    @pytest.fixture
    def create_table_query(self, table_name):
        query = ("CREATE TABLE `{table_name}` "
                 "(\n  `id` int(11) DEFAULT NULL,\n "
                 " `name` varchar(64) DEFAULT NULL\n) "
                 "ENGINE=InnoDB DEFAULT CHARSET=utf8").format(table_name=table_name)
        return query

    @pytest.fixture
    def avro_schema(self, table_name):
        return {
            u'fields': [
                {u'default': None, u'type': [u'null', u'int'], u'name': u'id'},
                {u'default': None, u'maxlen': u'64', u'type': [u'null', u'string'], u'name': u'name'}
            ],
            u'namespace': u'',
            u'name': table_name,
            u'type': u'record'
        }

    def test_create_table(
        self,
        containers,
        create_table_query,
        avro_schema,
        table_name,
        namespace,
        schematizer,
    ):
        old_heartbeat = 0
        new_heartbeat = 123
        set_heartbeat(containers, old_heartbeat, new_heartbeat)
        execute_query_get_one_row(containers, RBR_SOURCE, create_table_query)

        # Need to poll for the creation of the table
        self._wait_for_table(containers, SCHEMA_TRACKER, table_name)

        # Check the schematracker db also has the table.
        verify_create_table_query = "SHOW CREATE TABLE {table_name}".format(
            table_name=table_name)
        verify_create_table_result = execute_query_get_one_row(containers, SCHEMA_TRACKER, verify_create_table_query)
        expected_create_table_result = {
            'Table': table_name,
            'Create Table': create_table_query
        }
        self.assert_expected_result(verify_create_table_result, expected_create_table_result)

        # Check schematizer.
        self.check_schematizer_has_correct_source_info(
            table_name=table_name,
            avro_schema=avro_schema,
            namespace=namespace,
            schematizer=schematizer
        )

    def _wait_for_table(self, containers, db_name, table_name):
        poll_query = "SHOW TABLES LIKE '{table_name}'".format(table_name=table_name)
        timeout_seconds = 60
        end_time = time.time() + timeout_seconds
        while end_time > time.time():
            result = execute_query_get_one_row(containers, db_name, poll_query)
            if result is not None:
                break
            time.sleep(0.5)

    def check_schematizer_has_correct_source_info(
        self,
        table_name,
        avro_schema,
        namespace,
        schematizer
    ):
        sources = schematizer.get_sources_by_namespace(namespace)
        source = next(src for src in reversed(sources) if src.name == table_name)
        topic = schematizer.get_topics_by_source_id(source.source_id)[-1]
        schema = schematizer.get_latest_schema_by_topic_name(topic.name)
        assert schema.topic.source.name == table_name
        assert schema.topic.source.namespace.name == namespace
        assert schema.schema_json == avro_schema

    def assert_expected_result(self, result, expected):
        for key, value in expected.iteritems():
            assert result[key] == value