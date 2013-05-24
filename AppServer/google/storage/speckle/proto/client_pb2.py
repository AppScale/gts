#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#



from google.net.proto2.python.internal import enum_type_wrapper
from google.net.proto2.python.public import descriptor as _descriptor
from google.net.proto2.python.public import message as _message
from google.net.proto2.python.public import reflection as _reflection
from google.net.proto2.proto import descriptor_pb2





DESCRIPTOR = _descriptor.FileDescriptor(
  name='storage/speckle/proto/client.proto',
  package='speckle',
  serialized_pb='\n\"storage/speckle/proto/client.proto\x12\x07speckle\"\xb6\x01\n\x11\x42indVariableProto\x12\r\n\x05value\x18\x01 \x01(\x0c\x12\x0c\n\x04type\x18\x02 \x01(\x05\x12\x10\n\x08position\x18\x03 \x01(\x05\x12\x0c\n\x04name\x18\x04 \x01(\t\x12;\n\tdirection\x18\x05 \x01(\x0e\x32$.speckle.BindVariableProto.Direction:\x02IN\"\'\n\tDirection\x12\x06\n\x02IN\x10\x01\x12\x07\n\x03OUT\x10\x02\x12\t\n\x05INOUT\x10\x03\"\x8c\x03\n\x0bResultProto\x12\"\n\x04rows\x18\x01 \x01(\x0b\x32\x14.speckle.RowSetProto\x12\x14\n\x0crows_updated\x18\x02 \x01(\x03\x12\x16\n\x0egenerated_keys\x18\x03 \x03(\x0c\x12\'\n\x08warnings\x18\x04 \x03(\x0b\x32\x15.speckle.SqlException\x12,\n\rsql_exception\x18\x05 \x01(\x0b\x32\x15.speckle.SqlException\x12\x14\n\x0cstatement_id\x18\x06 \x01(\x04\x12\x18\n\tmore_rows\x18\x07 \x01(\x08:\x05\x66\x61lse\x12\x1b\n\x0cmore_results\x18\x08 \x01(\x08:\x05\x66\x61lse\x12\x33\n\x0foutput_variable\x18\t \x03(\x0b\x32\x1a.speckle.BindVariableProto\x12\x1a\n\x12\x62\x61tch_rows_updated\x18\n \x03(\x03\x12\x36\n\x12parameter_metadata\x18\x0b \x03(\x0b\x32\x1a.speckle.ParameterMetadata\"\xf1\x05\n\x07OpProto\x12%\n\x04type\x18\x01 \x02(\x0e\x32\x17.speckle.OpProto.OpType\x12\x0f\n\x07\x63\x61talog\x18\x02 \x01(\t\x12\x0b\n\x03sql\x18\x03 \x01(\t\x12%\n\tsavepoint\x18\x04 \x01(\x0b\x32\x12.speckle.SavePoint\x12\x13\n\x0b\x61uto_commit\x18\x05 \x01(\x08\x12\x11\n\tread_only\x18\x06 \x01(\x08\x12G\n\x1btransaction_isolation_level\x18\x07 \x01(\x0e\x32\".speckle.TransactionIsolationLevel\x12\x14\n\x0cstatement_id\x18\x08 \x01(\x04\x12\x12\n\nrequest_id\x18\t \x01(\x04\"\xde\x03\n\x06OpType\x12\x0e\n\nNATIVE_SQL\x10\x01\x12\x0c\n\x08ROLLBACK\x10\x02\x12\x11\n\rSET_SAVEPOINT\x10\x03\x12\x13\n\x0fSET_AUTO_COMMIT\x10\x04\x12\x11\n\rSET_READ_ONLY\x10\x05\x12#\n\x1fSET_TRANSACTION_ISOLATION_LEVEL\x10\x06\x12\n\n\x06\x43OMMIT\x10\x07\x12\x0f\n\x0bSET_CATALOG\x10\x08\x12\x13\n\x0f\x43LOSE_STATEMENT\x10\t\x12\x08\n\x04PING\x10\n\x12\x0f\n\x0bNEXT_RESULT\x10\x0b\x12\t\n\x05RETRY\x10\x0c\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE13\x10\r\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE14\x10\x0e\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE15\x10\x0f\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE16\x10\x10\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE17\x10\x11\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE18\x10\x12\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE19\x10\x13\x12\x1e\n\x1aVALUE_ENUM_UNKNOWN_VALUE20\x10\x14\"%\n\tSavePoint\x12\n\n\x02id\x18\x01 \x01(\x03\x12\x0c\n\x04name\x18\x02 \x02(\t\"c\n\x0cSqlException\x12\x0f\n\x07message\x18\x01 \x02(\t\x12\x0f\n\x04\x63ode\x18\x02 \x02(\x05:\x01\x30\x12\x11\n\tsql_state\x18\x03 \x01(\t\x12\x1e\n\x16\x61pplication_error_code\x18\x04 \x01(\x05\"+\n\nTupleProto\x12\x0e\n\x06values\x18\x01 \x03(\x0c\x12\r\n\x05nulls\x18\x02 \x03(\x05\"\xc0\x03\n\x0b\x43olumnProto\x12\x0c\n\x04name\x18\x01 \x02(\t\x12\r\n\x05label\x18\x02 \x01(\t\x12\x10\n\x04type\x18\x03 \x01(\x05:\x02\x31\x32\x12\x12\n\ntable_name\x18\x04 \x01(\t\x12\x13\n\x0bschema_name\x18\x05 \x01(\t\x12\x14\n\x0c\x63\x61talog_name\x18\x06 \x01(\t\x12\x14\n\tprecision\x18\x07 \x01(\x05:\x01\x30\x12\x10\n\x05scale\x18\x08 \x01(\x05:\x01\x30\x12\x10\n\x08nullable\x18\t \x01(\x08\x12\x12\n\nsearchable\x18\n \x01(\x08\x12\x14\n\x0c\x64isplay_size\x18\x0b \x01(\x05\x12\x1d\n\x0e\x61uto_increment\x18\x0c \x01(\x08:\x05\x66\x61lse\x12\x1d\n\x0e\x63\x61se_sensitive\x18\r \x01(\x08:\x05\x66\x61lse\x12\x17\n\x08\x63urrency\x18\x0e \x01(\x08:\x05\x66\x61lse\x12\"\n\x13\x64\x65\x66initely_writable\x18\x0f \x01(\x08:\x05\x66\x61lse\x12\x18\n\tread_only\x18\x10 \x01(\x08:\x05\x66\x61lse\x12\x15\n\x06signed\x18\x11 \x01(\x08:\x05\x66\x61lse\x12\x17\n\x08writable\x18\x12 \x01(\x08:\x05\x66\x61lse\x12\x1a\n\x10\x63olumn_type_name\x18\x13 \x01(\t:\x00\"Y\n\x0bRowSetProto\x12%\n\x07\x63olumns\x18\x01 \x03(\x0b\x32\x14.speckle.ColumnProto\x12#\n\x06tuples\x18\x02 \x03(\x0b\x32\x13.speckle.TupleProto\"\xcb\x36\n\x19JdbcDatabaseMetaDataProto\x12*\n\x1b\x61ll_procedures_are_callable\x18\x01 \x01(\x08:\x05\x66\x61lse\x12(\n\x19\x61ll_tables_are_selectable\x18\x02 \x01(\x08:\x05\x66\x61lse\x12\x39\n*auto_commit_failure_closes_all_result_sets\x18\x03 \x01(\x08:\x05\x66\x61lse\x12\x38\n)data_definition_causes_transaction_commit\x18\x04 \x01(\x08:\x05\x66\x61lse\x12\x36\n\'data_definition_ignored_in_transactions\x18\x05 \x01(\x08:\x05\x66\x61lse\x12.\n\x1f\x64oes_max_row_size_include_blobs\x18\x06 \x01(\x08:\x05\x66\x61lse\x12\x19\n\x11\x63\x61talog_separator\x18\x07 \x01(\t\x12\x14\n\x0c\x63\x61talog_term\x18\x08 \x01(\t\x12!\n\x16\x64\x61tabase_major_version\x18\t \x01(\x05:\x01\x30\x12!\n\x16\x64\x61tabase_minor_version\x18\n \x01(\x05:\x01\x30\x12&\n\x15\x64\x61tabase_product_name\x18\x0b \x01(\t:\x07Speckle\x12\"\n\x18\x64\x61tabase_product_version\x18\x0c \x01(\t:\x00\x12u\n\x1d\x64\x65\x66\x61ult_transaction_isolation\x18\r \x01(\x0e\x32\".speckle.TransactionIsolationLevel:*TRANSACTIONISOLATIONLEVEL_TRANSACTION_NONE\x12\x1f\n\x15\x65xtra_name_characters\x18\x0e \x01(\t:\x00\x12!\n\x17identifier_quote_string\x18\x0f \x01(\t:\x00\x12\x1d\n\x12jdbc_major_version\x18\x10 \x01(\x05:\x01\x31\x12\x1d\n\x12jdbc_minor_version\x18\x11 \x01(\x05:\x01\x30\x12$\n\x19max_binary_literal_length\x18\x12 \x01(\x05:\x01\x30\x12\"\n\x17max_catalog_name_length\x18\x13 \x01(\x05:\x01\x30\x12\"\n\x17max_char_literal_length\x18\x14 \x01(\x05:\x01\x30\x12!\n\x16max_column_name_length\x18\x15 \x01(\x05:\x01\x30\x12\"\n\x17max_columns_in_group_by\x18\x16 \x01(\x05:\x01\x30\x12\x1f\n\x14max_columns_in_index\x18\x17 \x01(\x05:\x01\x30\x12\"\n\x17max_columns_in_order_by\x18\x18 \x01(\x05:\x01\x30\x12 \n\x15max_columns_in_select\x18\x19 \x01(\x05:\x01\x30\x12\x1f\n\x14max_columns_in_table\x18\x1a \x01(\x05:\x01\x30\x12\x1a\n\x0fmax_connections\x18\x1b \x01(\x05:\x01\x30\x12!\n\x16max_cursor_name_length\x18\x1c \x01(\x05:\x01\x30\x12\x1b\n\x10max_index_length\x18\x1d \x01(\x05:\x01\x30\x12$\n\x19max_procedure_name_length\x18\x1e \x01(\x05:\x01\x30\x12\x17\n\x0cmax_row_size\x18\x1f \x01(\x05:\x01\x30\x12!\n\x16max_schema_name_length\x18  \x01(\x05:\x01\x30\x12\x1f\n\x14max_statement_length\x18! \x01(\x05:\x01\x30\x12\x19\n\x0emax_statements\x18\" \x01(\x05:\x01\x30\x12 \n\x15max_table_name_length\x18# \x01(\x05:\x01\x30\x12\x1f\n\x14max_tables_in_select\x18$ \x01(\x05:\x01\x30\x12\x1f\n\x14max_user_name_length\x18% \x01(\x05:\x01\x30\x12\x1b\n\x11numeric_functions\x18& \x01(\t:\x00\x12\x18\n\x0eprocedure_term\x18\' \x01(\t:\x00\x12j\n\x15resultset_holdability\x18( \x01(\x0e\x32\x1d.speckle.ResultSetHoldability:,RESULTSETHOLDABILITY_CLOSE_CURSORS_AT_COMMIT\x12i\n\x0erowid_lifetime\x18) \x01(\x0e\x32\x30.speckle.JdbcDatabaseMetaDataProto.RowIdLifetime:\x1fROWIDLIFETIME_ROWID_UNSUPPORTED\x12\x14\n\x0csql_keywords\x18* \x01(\t\x12\x63\n\x0esql_state_type\x18+ \x01(\x0e\x32/.speckle.JdbcDatabaseMetaDataProto.SqlStateType:\x1aSQLSTATETYPE_SQL_STATE_SQL\x12\x15\n\x0bschema_term\x18, \x01(\t:\x00\x12\x1c\n\x14search_string_escape\x18- \x01(\t\x12\x1a\n\x10string_functions\x18. \x01(\t:\x00\x12\x1a\n\x10system_functions\x18/ \x01(\t:\x00\x12\x1d\n\x13time_date_functions\x18\x30 \x01(\t:\x00\x12\x13\n\tuser_name\x18\x31 \x01(\t:\x00\x12\x1f\n\x10\x63\x61talog_at_start\x18\x32 \x01(\x08:\x05\x66\x61lse\x12#\n\x14locators_update_copy\x18\x33 \x01(\x08:\x05\x66\x61lse\x12)\n\x1anull_plus_non_null_is_null\x18\x34 \x01(\x08:\x05\x66\x61lse\x12&\n\x17nulls_are_sorted_at_end\x18\x35 \x01(\x08:\x05\x66\x61lse\x12(\n\x19nulls_are_sorted_at_start\x18\x36 \x01(\x08:\x05\x66\x61lse\x12$\n\x15nulls_are_sorted_high\x18\x37 \x01(\x08:\x05\x66\x61lse\x12#\n\x14nulls_are_sorted_low\x18\x38 \x01(\x08:\x05\x66\x61lse\x12,\n\x1dstores_lower_case_identifiers\x18\x39 \x01(\x08:\x05\x66\x61lse\x12\x33\n$stores_lower_case_quoted_identifiers\x18: \x01(\x08:\x05\x66\x61lse\x12,\n\x1dstores_mixed_case_identifiers\x18; \x01(\x08:\x05\x66\x61lse\x12\x33\n$stores_mixed_case_quoted_identifiers\x18< \x01(\x08:\x05\x66\x61lse\x12,\n\x1dstores_upper_case_identifiers\x18= \x01(\x08:\x05\x66\x61lse\x12\x33\n$stores_upper_case_quoted_identifiers\x18> \x01(\x08:\x05\x66\x61lse\x12.\n\x1fsupports_ansi92_entry_level_sql\x18? \x01(\x08:\x05\x66\x61lse\x12\'\n\x18supports_ansi92_full_sql\x18@ \x01(\x08:\x05\x66\x61lse\x12/\n supports_ansi92_intermediate_sql\x18\x41 \x01(\x08:\x05\x66\x61lse\x12\x33\n$supports_alter_table_with_add_column\x18\x42 \x01(\x08:\x05\x66\x61lse\x12\x34\n%supports_alter_table_with_drop_column\x18\x43 \x01(\x08:\x05\x66\x61lse\x12%\n\x16supports_batch_updates\x18\x44 \x01(\x08:\x05\x66\x61lse\x12\x35\n&supports_catalogs_in_data_manipulation\x18\x45 \x01(\x08:\x05\x66\x61lse\x12\x35\n&supports_catalogs_in_index_definitions\x18\x46 \x01(\x08:\x05\x66\x61lse\x12\x39\n*supports_catalogs_in_privilege_definitions\x18G \x01(\x08:\x05\x66\x61lse\x12\x33\n$supports_catalogs_in_procedure_calls\x18H \x01(\x08:\x05\x66\x61lse\x12\x35\n&supports_catalogs_in_table_definitions\x18I \x01(\x08:\x05\x66\x61lse\x12\'\n\x18supports_column_aliasing\x18J \x01(\x08:\x05\x66\x61lse\x12\x1f\n\x10supports_convert\x18K \x01(\x08:\x05\x66\x61lse\x12(\n\x19supports_core_sql_grammar\x18L \x01(\x08:\x05\x66\x61lse\x12-\n\x1esupports_correlated_subqueries\x18M \x01(\x08:\x05\x66\x61lse\x12J\n;supports_data_definition_and_data_manipulation_transactions\x18N \x01(\x08:\x05\x66\x61lse\x12;\n,supports_data_manipulation_transactions_only\x18O \x01(\x08:\x05\x66\x61lse\x12\x39\n*supports_different_table_correlation_names\x18P \x01(\x08:\x05\x66\x61lse\x12/\n supports_expressions_in_order_by\x18Q \x01(\x08:\x05\x66\x61lse\x12,\n\x1dsupports_extended_sql_grammar\x18R \x01(\x08:\x05\x66\x61lse\x12(\n\x19supports_full_outer_joins\x18S \x01(\x08:\x05\x66\x61lse\x12*\n\x1bsupports_get_generated_keys\x18T \x01(\x08:\x05\x66\x61lse\x12 \n\x11supports_group_by\x18U \x01(\x08:\x05\x66\x61lse\x12.\n\x1fsupports_group_by_beyond_select\x18V \x01(\x08:\x05\x66\x61lse\x12*\n\x1bsupports_group_by_unrelated\x18W \x01(\x08:\x05\x66\x61lse\x12\x36\n\'supports_integrity_enhancement_facility\x18X \x01(\x08:\x05\x66\x61lse\x12*\n\x1bsupports_like_escape_clause\x18Y \x01(\x08:\x05\x66\x61lse\x12+\n\x1csupports_limited_outer_joins\x18Z \x01(\x08:\x05\x66\x61lse\x12+\n\x1csupports_minimum_sql_grammar\x18[ \x01(\x08:\x05\x66\x61lse\x12.\n\x1fsupports_mixed_case_identifiers\x18\\ \x01(\x08:\x05\x66\x61lse\x12\x35\n&supports_mixed_case_quoted_identifiers\x18] \x01(\x08:\x05\x66\x61lse\x12-\n\x1esupports_multiple_open_results\x18^ \x01(\x08:\x05\x66\x61lse\x12,\n\x1dsupports_multiple_result_sets\x18_ \x01(\x08:\x05\x66\x61lse\x12-\n\x1esupports_multiple_transactions\x18` \x01(\x08:\x05\x66\x61lse\x12(\n\x19supports_named_parameters\x18\x61 \x01(\x08:\x05\x66\x61lse\x12,\n\x1dsupports_non_nullable_columns\x18\x62 \x01(\x08:\x05\x66\x61lse\x12\x32\n#supports_open_cursors_across_commit\x18\x63 \x01(\x08:\x05\x66\x61lse\x12\x34\n%supports_open_cursors_across_rollback\x18\x64 \x01(\x08:\x05\x66\x61lse\x12\x35\n&supports_open_statements_across_commit\x18\x65 \x01(\x08:\x05\x66\x61lse\x12\x37\n(supports_open_statements_across_rollback\x18\x66 \x01(\x08:\x05\x66\x61lse\x12*\n\x1bsupports_order_by_unrelated\x18g \x01(\x08:\x05\x66\x61lse\x12#\n\x14supports_outer_joins\x18h \x01(\x08:\x05\x66\x61lse\x12)\n\x1asupports_positioned_delete\x18i \x01(\x08:\x05\x66\x61lse\x12)\n\x1asupports_positioned_update\x18j \x01(\x08:\x05\x66\x61lse\x12\"\n\x13supports_savepoints\x18k \x01(\x08:\x05\x66\x61lse\x12\x34\n%supports_schemas_in_data_manipulation\x18l \x01(\x08:\x05\x66\x61lse\x12\x34\n%supports_schemas_in_index_definitions\x18m \x01(\x08:\x05\x66\x61lse\x12\x38\n)supports_schemas_in_privilege_definitions\x18n \x01(\x08:\x05\x66\x61lse\x12\x32\n#supports_schemas_in_procedure_calls\x18o \x01(\x08:\x05\x66\x61lse\x12\x34\n%supports_schemas_in_table_definitions\x18p \x01(\x08:\x05\x66\x61lse\x12)\n\x1asupports_select_for_update\x18q \x01(\x08:\x05\x66\x61lse\x12)\n\x1asupports_statement_pooling\x18r \x01(\x08:\x05\x66\x61lse\x12:\n+supports_stored_functions_using_call_syntax\x18s \x01(\x08:\x05\x66\x61lse\x12)\n\x1asupports_stored_procedures\x18t \x01(\x08:\x05\x66\x61lse\x12\x31\n\"supports_subqueries_in_comparisons\x18u \x01(\x08:\x05\x66\x61lse\x12,\n\x1dsupports_subqueries_in_exists\x18v \x01(\x08:\x05\x66\x61lse\x12)\n\x1asupports_subqueries_in_ins\x18w \x01(\x08:\x05\x66\x61lse\x12\x31\n\"supports_subqueries_in_quantifieds\x18x \x01(\x08:\x05\x66\x61lse\x12/\n supports_table_correlation_names\x18y \x01(\x08:\x05\x66\x61lse\x12$\n\x15supports_transactions\x18z \x01(\x08:\x05\x66\x61lse\x12\x1d\n\x0esupports_union\x18{ \x01(\x08:\x05\x66\x61lse\x12!\n\x12supports_union_all\x18| \x01(\x08:\x05\x66\x61lse\x12(\n\x19uses_local_file_per_table\x18} \x01(\x08:\x05\x66\x61lse\x12\x1f\n\x10uses_local_files\x18~ \x01(\x08:\x05\x66\x61lse\x12\x18\n\tread_only\x18\x7f \x01(\x08:\x05\x66\x61lse\x12\x14\n\x0btable_types\x18\x80\x01 \x03(\t\x12\x11\n\x08\x63\x61talogs\x18\x81\x01 \x03(\t\x12;\n\x07schemas\x18\x82\x01 \x03(\x0b\x32).speckle.JdbcDatabaseMetaDataProto.Schema\x12\x35\n\x14\x64\x65letes_are_detected\x18\x83\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12\x35\n\x14inserts_are_detected\x18\x84\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12\x35\n\x14updates_are_detected\x18\x85\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12;\n\x1aothers_deletes_are_visible\x18\x86\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12;\n\x1aothers_inserts_are_visible\x18\x87\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12;\n\x1aothers_updates_are_visible\x18\x88\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12\x38\n\x17own_deletes_are_visible\x18\x89\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12\x38\n\x17own_inserts_are_visible\x18\x8a\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12\x38\n\x17own_updates_are_visible\x18\x8b\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12J\n)supports_result_set_concurrency_updatable\x18\x8c\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12\x39\n\x18supports_result_set_type\x18\x8d\x01 \x03(\x0e\x32\x16.speckle.ResultSetType\x12G\n\x1fsupports_result_set_holdability\x18\x8e\x01 \x03(\x0e\x32\x1d.speckle.ResultSetHoldability\x12Q\n$supports_transaction_isolation_level\x18\x8f\x01 \x03(\x0e\x32\".speckle.TransactionIsolationLevel\x12-\n\x1dgenerated_key_always_returned\x18\x90\x01 \x01(\x08:\x05\x66\x61lse\x1a\x35\n\x06Schema\x12\x14\n\x0ctable_schema\x18\x01 \x01(\t\x12\x15\n\rtable_catalog\x18\x02 \x01(\t\"\xd2\x01\n\rRowIdLifetime\x12#\n\x1fROWIDLIFETIME_ROWID_UNSUPPORTED\x10\x00\x12%\n!ROWIDLIFETIME_ROWID_VALID_FOREVER\x10\x01\x12#\n\x1fROWIDLIFETIME_ROWID_VALID_OTHER\x10\x02\x12%\n!ROWIDLIFETIME_ROWID_VALID_SESSION\x10\x03\x12)\n%ROWIDLIFETIME_ROWID_VALID_TRANSACTION\x10\x04\"r\n\x0cSqlStateType\x12\x1e\n\x1aSQLSTATETYPE_SQL_STATE_SQL\x10\x00\x12 \n\x1cSQLSTATETYPE_SQL_STATE_SQL99\x10\x01\x12 \n\x1cSQLSTATETYPE_SQL_STATE_XOPEN\x10\x02\"&\n\x08Property\x12\x0b\n\x03key\x18\x01 \x02(\t\x12\r\n\x05value\x18\x02 \x01(\t\"\xd6\x03\n\x0b\x45xecOptions\x12%\n\x16include_generated_keys\x18\x01 \x01(\x08:\x05\x66\x61lse\x12 \n\x18generated_column_indices\x18\x02 \x03(\x05\x12\x1e\n\x16generated_column_names\x18\x03 \x03(\t\x12$\n\x04type\x18\x04 \x01(\x0e\x32\x16.speckle.ResultSetType\x12\x32\n\x0b\x63oncurrency\x18\x05 \x01(\x0e\x32\x1d.speckle.ResultSetConcurrency\x12\x32\n\x0bholdability\x18\x06 \x01(\x0e\x32\x1d.speckle.ResultSetHoldability\x12\x12\n\nfetch_size\x18\x07 \x01(\x05\x12\x10\n\x08max_rows\x18\x08 \x01(\x05\x12\x17\n\x08poolable\x18\t \x01(\x08:\x05\x66\x61lse\x12?\n\x0f\x66\x65tch_direction\x18\n \x01(\x0e\x32\x17.speckle.FetchDirection:\rFETCH_FORWARD\x12\x13\n\x0b\x63ursor_name\x18\x0b \x01(\t\x12\x19\n\x0emax_field_size\x18\x0c \x01(\x05:\x01\x30\x12 \n\x11\x65scape_processing\x18\r \x01(\x08:\x05\x66\x61lse\"K\n\x16\x42\x61tchBindVariableProto\x12\x31\n\rbind_variable\x18\x01 \x03(\x0b\x32\x1a.speckle.BindVariableProto\"]\n\nBatchProto\x12\x11\n\tstatement\x18\x01 \x03(\t\x12<\n\x13\x62\x61tch_bind_variable\x18\x02 \x03(\x0b\x32\x1f.speckle.BatchBindVariableProto\"!\n\x11ParameterMetadata\x12\x0c\n\x04name\x18\x01 \x01(\t\":\n\rRpcErrorProto\x12\x12\n\nerror_code\x18\x01 \x01(\x05\x12\x15\n\rerror_message\x18\x02 \x01(\t*\xb4\x02\n\x19TransactionIsolationLevel\x12.\n*TRANSACTIONISOLATIONLEVEL_TRANSACTION_NONE\x10\x00\x12\x38\n4TRANSACTIONISOLATIONLEVEL_TRANSACTION_READ_COMMITTED\x10\x02\x12:\n6TRANSACTIONISOLATIONLEVEL_TRANSACTION_READ_UNCOMMITTED\x10\x01\x12\x39\n5TRANSACTIONISOLATIONLEVEL_TRANSACTION_REPEATABLE_READ\x10\x04\x12\x36\n2TRANSACTIONISOLATIONLEVEL_TRANSACTION_SERIALIZABLE\x10\x08*\x8b\x01\n\rResultSetType\x12$\n\x1fRESULTSETTYPE_TYPE_FORWARD_ONLY\x10\xeb\x07\x12*\n%RESULTSETTYPE_TYPE_SCROLL_INSENSITIVE\x10\xec\x07\x12(\n#RESULTSETTYPE_TYPE_SCROLL_SENSITIVE\x10\xed\x07*n\n\x14ResultSetConcurrency\x12*\n%RESULTSETCONCURRENCY_CONCUR_READ_ONLY\x10\xef\x07\x12*\n%RESULTSETCONCURRENCY_CONCUR_UPDATABLE\x10\xf0\x07*{\n\x14ResultSetHoldability\x12\x31\n-RESULTSETHOLDABILITY_HOLD_CURSORS_OVER_COMMIT\x10\x01\x12\x30\n,RESULTSETHOLDABILITY_CLOSE_CURSORS_AT_COMMIT\x10\x02*L\n\x0e\x46\x65tchDirection\x12\x12\n\rFETCH_FORWARD\x10\xe8\x07\x12\x12\n\rFETCH_REVERSE\x10\xe9\x07\x12\x12\n\rFETCH_UNKNOWN\x10\xea\x07*\xc4\t\n\x0cMetadataType\x12(\n$METADATATYPE_DATABASE_METADATA_BASIC\x10\x01\x12-\n)METADATATYPE_DATABASE_METADATA_GET_TABLES\x10\x02\x12\x31\n-METADATATYPE_DATABASE_METADATA_GET_PROCEDURES\x10\x03\x12\x38\n4METADATATYPE_DATABASE_METADATA_GET_PROCEDURE_COLUMNS\x10\x04\x12.\n*METADATATYPE_DATABASE_METADATA_GET_COLUMNS\x10\x05\x12\x38\n4METADATATYPE_DATABASE_METADATA_GET_COLUMN_PRIVILEGES\x10\x06\x12\x37\n3METADATATYPE_DATABASE_METADATA_GET_TABLE_PRIVILEGES\x10\x07\x12:\n6METADATATYPE_DATABASE_METADATA_GET_BEST_ROW_IDENTIFIER\x10\x08\x12\x36\n2METADATATYPE_DATABASE_METADATA_GET_VERSION_COLUMNS\x10\t\x12\x33\n/METADATATYPE_DATABASE_METADATA_GET_PRIMARY_KEYS\x10\n\x12\x34\n0METADATATYPE_DATABASE_METADATA_GET_IMPORTED_KEYS\x10\x0b\x12\x34\n0METADATATYPE_DATABASE_METADATA_GET_EXPORTED_KEYS\x10\x0c\x12\x36\n2METADATATYPE_DATABASE_METADATA_GET_CROSS_REFERENCE\x10\r\x12\x31\n-METADATATYPE_DATABASE_METADATA_GET_INDEX_INFO\x10\x0e\x12+\n\'METADATATYPE_DATABASE_METADATA_GET_UDTS\x10\x0f\x12\x32\n.METADATATYPE_DATABASE_METADATA_GET_SUPER_TYPES\x10\x10\x12\x33\n/METADATATYPE_DATABASE_METADATA_GET_SUPER_TABLES\x10\x11\x12\x31\n-METADATATYPE_DATABASE_METADATA_GET_ATTRIBUTES\x10\x12\x12\x30\n,METADATATYPE_DATABASE_METADATA_GET_FUNCTIONS\x10\x13\x12\x37\n3METADATATYPE_DATABASE_METADATA_GET_FUNCTION_COLUMNS\x10\x14\x12\x30\n,METADATATYPE_DATABASE_METADATA_GET_TYPE_INFO\x10\x15\x12.\n*METADATATYPE_DATABASE_METADATA_GET_SCHEMAS\x10\x16\x12\x35\n1METADATATYPE_DATABASE_METADATA_GET_PSEUDO_COLUMNS\x10\x17*\xdb\x02\n\nClientType\x12\x19\n\x15\x43LIENT_TYPE_JAVA_JDBC\x10\x01\x12\x1c\n\x18\x43LIENT_TYPE_PYTHON_DBAPI\x10\x02\x12\x17\n\x13\x43LIENT_TYPE_UNKNOWN\x10\x03\x12\x12\n\x0e\x43LIENT_TYPE_GO\x10\x04\x12\x1e\n\x1a\x43LIENT_TYPE_EXPERIMENTAL_1\x10\x05\x12\x16\n\x12\x43LIENT_TYPE_NATIVE\x10\x06\x12!\n\x1d\x43LIENT_TYPE_UNKNOWN_LANGUAGE7\x10\x07\x12!\n\x1d\x43LIENT_TYPE_UNKNOWN_LANGUAGE8\x10\x08\x12!\n\x1d\x43LIENT_TYPE_UNKNOWN_LANGUAGE9\x10\t\x12\"\n\x1e\x43LIENT_TYPE_UNKNOWN_LANGUAGE10\x10\n\x12\"\n\x1e\x43LIENT_TYPE_UNKNOWN_LANGUAGE11\x10\x0b\x42%\n\x1b\x63om.google.protos.cloud.sql\x10\x02 \x02(\x02xd')

_TRANSACTIONISOLATIONLEVEL = _descriptor.EnumDescriptor(
  name='TransactionIsolationLevel',
  full_name='speckle.TransactionIsolationLevel',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='TRANSACTIONISOLATIONLEVEL_TRANSACTION_NONE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TRANSACTIONISOLATIONLEVEL_TRANSACTION_READ_COMMITTED', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TRANSACTIONISOLATIONLEVEL_TRANSACTION_READ_UNCOMMITTED', index=2, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TRANSACTIONISOLATIONLEVEL_TRANSACTION_REPEATABLE_READ', index=3, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TRANSACTIONISOLATIONLEVEL_TRANSACTION_SERIALIZABLE', index=4, number=8,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=9885,
  serialized_end=10193,
)

TransactionIsolationLevel = enum_type_wrapper.EnumTypeWrapper(_TRANSACTIONISOLATIONLEVEL)
_RESULTSETTYPE = _descriptor.EnumDescriptor(
  name='ResultSetType',
  full_name='speckle.ResultSetType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='RESULTSETTYPE_TYPE_FORWARD_ONLY', index=0, number=1003,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESULTSETTYPE_TYPE_SCROLL_INSENSITIVE', index=1, number=1004,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESULTSETTYPE_TYPE_SCROLL_SENSITIVE', index=2, number=1005,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=10196,
  serialized_end=10335,
)

ResultSetType = enum_type_wrapper.EnumTypeWrapper(_RESULTSETTYPE)
_RESULTSETCONCURRENCY = _descriptor.EnumDescriptor(
  name='ResultSetConcurrency',
  full_name='speckle.ResultSetConcurrency',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='RESULTSETCONCURRENCY_CONCUR_READ_ONLY', index=0, number=1007,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESULTSETCONCURRENCY_CONCUR_UPDATABLE', index=1, number=1008,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=10337,
  serialized_end=10447,
)

ResultSetConcurrency = enum_type_wrapper.EnumTypeWrapper(_RESULTSETCONCURRENCY)
_RESULTSETHOLDABILITY = _descriptor.EnumDescriptor(
  name='ResultSetHoldability',
  full_name='speckle.ResultSetHoldability',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='RESULTSETHOLDABILITY_HOLD_CURSORS_OVER_COMMIT', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESULTSETHOLDABILITY_CLOSE_CURSORS_AT_COMMIT', index=1, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=10449,
  serialized_end=10572,
)

ResultSetHoldability = enum_type_wrapper.EnumTypeWrapper(_RESULTSETHOLDABILITY)
_FETCHDIRECTION = _descriptor.EnumDescriptor(
  name='FetchDirection',
  full_name='speckle.FetchDirection',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='FETCH_FORWARD', index=0, number=1000,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FETCH_REVERSE', index=1, number=1001,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FETCH_UNKNOWN', index=2, number=1002,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=10574,
  serialized_end=10650,
)

FetchDirection = enum_type_wrapper.EnumTypeWrapper(_FETCHDIRECTION)
_METADATATYPE = _descriptor.EnumDescriptor(
  name='MetadataType',
  full_name='speckle.MetadataType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_BASIC', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_TABLES', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_PROCEDURES', index=2, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_PROCEDURE_COLUMNS', index=3, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_COLUMNS', index=4, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_COLUMN_PRIVILEGES', index=5, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_TABLE_PRIVILEGES', index=6, number=7,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_BEST_ROW_IDENTIFIER', index=7, number=8,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_VERSION_COLUMNS', index=8, number=9,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_PRIMARY_KEYS', index=9, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_IMPORTED_KEYS', index=10, number=11,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_EXPORTED_KEYS', index=11, number=12,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_CROSS_REFERENCE', index=12, number=13,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_INDEX_INFO', index=13, number=14,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_UDTS', index=14, number=15,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_SUPER_TYPES', index=15, number=16,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_SUPER_TABLES', index=16, number=17,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_ATTRIBUTES', index=17, number=18,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_FUNCTIONS', index=18, number=19,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_FUNCTION_COLUMNS', index=19, number=20,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_TYPE_INFO', index=20, number=21,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_SCHEMAS', index=21, number=22,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='METADATATYPE_DATABASE_METADATA_GET_PSEUDO_COLUMNS', index=22, number=23,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=10653,
  serialized_end=11873,
)

MetadataType = enum_type_wrapper.EnumTypeWrapper(_METADATATYPE)
_CLIENTTYPE = _descriptor.EnumDescriptor(
  name='ClientType',
  full_name='speckle.ClientType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_JAVA_JDBC', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_PYTHON_DBAPI', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_UNKNOWN', index=2, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_GO', index=3, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_EXPERIMENTAL_1', index=4, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_NATIVE', index=5, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_UNKNOWN_LANGUAGE7', index=6, number=7,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_UNKNOWN_LANGUAGE8', index=7, number=8,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_UNKNOWN_LANGUAGE9', index=8, number=9,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_UNKNOWN_LANGUAGE10', index=9, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT_TYPE_UNKNOWN_LANGUAGE11', index=10, number=11,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=11876,
  serialized_end=12223,
)

ClientType = enum_type_wrapper.EnumTypeWrapper(_CLIENTTYPE)
TRANSACTIONISOLATIONLEVEL_TRANSACTION_NONE = 0
TRANSACTIONISOLATIONLEVEL_TRANSACTION_READ_COMMITTED = 2
TRANSACTIONISOLATIONLEVEL_TRANSACTION_READ_UNCOMMITTED = 1
TRANSACTIONISOLATIONLEVEL_TRANSACTION_REPEATABLE_READ = 4
TRANSACTIONISOLATIONLEVEL_TRANSACTION_SERIALIZABLE = 8
RESULTSETTYPE_TYPE_FORWARD_ONLY = 1003
RESULTSETTYPE_TYPE_SCROLL_INSENSITIVE = 1004
RESULTSETTYPE_TYPE_SCROLL_SENSITIVE = 1005
RESULTSETCONCURRENCY_CONCUR_READ_ONLY = 1007
RESULTSETCONCURRENCY_CONCUR_UPDATABLE = 1008
RESULTSETHOLDABILITY_HOLD_CURSORS_OVER_COMMIT = 1
RESULTSETHOLDABILITY_CLOSE_CURSORS_AT_COMMIT = 2
FETCH_FORWARD = 1000
FETCH_REVERSE = 1001
FETCH_UNKNOWN = 1002
METADATATYPE_DATABASE_METADATA_BASIC = 1
METADATATYPE_DATABASE_METADATA_GET_TABLES = 2
METADATATYPE_DATABASE_METADATA_GET_PROCEDURES = 3
METADATATYPE_DATABASE_METADATA_GET_PROCEDURE_COLUMNS = 4
METADATATYPE_DATABASE_METADATA_GET_COLUMNS = 5
METADATATYPE_DATABASE_METADATA_GET_COLUMN_PRIVILEGES = 6
METADATATYPE_DATABASE_METADATA_GET_TABLE_PRIVILEGES = 7
METADATATYPE_DATABASE_METADATA_GET_BEST_ROW_IDENTIFIER = 8
METADATATYPE_DATABASE_METADATA_GET_VERSION_COLUMNS = 9
METADATATYPE_DATABASE_METADATA_GET_PRIMARY_KEYS = 10
METADATATYPE_DATABASE_METADATA_GET_IMPORTED_KEYS = 11
METADATATYPE_DATABASE_METADATA_GET_EXPORTED_KEYS = 12
METADATATYPE_DATABASE_METADATA_GET_CROSS_REFERENCE = 13
METADATATYPE_DATABASE_METADATA_GET_INDEX_INFO = 14
METADATATYPE_DATABASE_METADATA_GET_UDTS = 15
METADATATYPE_DATABASE_METADATA_GET_SUPER_TYPES = 16
METADATATYPE_DATABASE_METADATA_GET_SUPER_TABLES = 17
METADATATYPE_DATABASE_METADATA_GET_ATTRIBUTES = 18
METADATATYPE_DATABASE_METADATA_GET_FUNCTIONS = 19
METADATATYPE_DATABASE_METADATA_GET_FUNCTION_COLUMNS = 20
METADATATYPE_DATABASE_METADATA_GET_TYPE_INFO = 21
METADATATYPE_DATABASE_METADATA_GET_SCHEMAS = 22
METADATATYPE_DATABASE_METADATA_GET_PSEUDO_COLUMNS = 23
CLIENT_TYPE_JAVA_JDBC = 1
CLIENT_TYPE_PYTHON_DBAPI = 2
CLIENT_TYPE_UNKNOWN = 3
CLIENT_TYPE_GO = 4
CLIENT_TYPE_EXPERIMENTAL_1 = 5
CLIENT_TYPE_NATIVE = 6
CLIENT_TYPE_UNKNOWN_LANGUAGE7 = 7
CLIENT_TYPE_UNKNOWN_LANGUAGE8 = 8
CLIENT_TYPE_UNKNOWN_LANGUAGE9 = 9
CLIENT_TYPE_UNKNOWN_LANGUAGE10 = 10
CLIENT_TYPE_UNKNOWN_LANGUAGE11 = 11


_BINDVARIABLEPROTO_DIRECTION = _descriptor.EnumDescriptor(
  name='Direction',
  full_name='speckle.BindVariableProto.Direction',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='IN', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='OUT', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INOUT', index=2, number=3,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=191,
  serialized_end=230,
)

_OPPROTO_OPTYPE = _descriptor.EnumDescriptor(
  name='OpType',
  full_name='speckle.OpProto.OpType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='NATIVE_SQL', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ROLLBACK', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SET_SAVEPOINT', index=2, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SET_AUTO_COMMIT', index=3, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SET_READ_ONLY', index=4, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SET_TRANSACTION_ISOLATION_LEVEL', index=5, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='COMMIT', index=6, number=7,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SET_CATALOG', index=7, number=8,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLOSE_STATEMENT', index=8, number=9,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PING', index=9, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NEXT_RESULT', index=10, number=11,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RETRY', index=11, number=12,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE13', index=12, number=13,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE14', index=13, number=14,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE15', index=14, number=15,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE16', index=15, number=16,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE17', index=16, number=17,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE18', index=17, number=18,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE19', index=18, number=19,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='VALUE_ENUM_UNKNOWN_VALUE20', index=19, number=20,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=907,
  serialized_end=1385,
)

_JDBCDATABASEMETADATAPROTO_ROWIDLIFETIME = _descriptor.EnumDescriptor(
  name='RowIdLifetime',
  full_name='speckle.JdbcDatabaseMetaDataProto.RowIdLifetime',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='ROWIDLIFETIME_ROWID_UNSUPPORTED', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ROWIDLIFETIME_ROWID_VALID_FOREVER', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ROWIDLIFETIME_ROWID_VALID_OTHER', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ROWIDLIFETIME_ROWID_VALID_SESSION', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ROWIDLIFETIME_ROWID_VALID_TRANSACTION', index=4, number=4,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=8776,
  serialized_end=8986,
)

_JDBCDATABASEMETADATAPROTO_SQLSTATETYPE = _descriptor.EnumDescriptor(
  name='SqlStateType',
  full_name='speckle.JdbcDatabaseMetaDataProto.SqlStateType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='SQLSTATETYPE_SQL_STATE_SQL', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SQLSTATETYPE_SQL_STATE_SQL99', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SQLSTATETYPE_SQL_STATE_XOPEN', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=8988,
  serialized_end=9102,
)


_BINDVARIABLEPROTO = _descriptor.Descriptor(
  name='BindVariableProto',
  full_name='speckle.BindVariableProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='value', full_name='speckle.BindVariableProto.value', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type', full_name='speckle.BindVariableProto.type', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='position', full_name='speckle.BindVariableProto.position', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='name', full_name='speckle.BindVariableProto.name', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='direction', full_name='speckle.BindVariableProto.direction', index=4,
      number=5, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _BINDVARIABLEPROTO_DIRECTION,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=48,
  serialized_end=230,
)


_RESULTPROTO = _descriptor.Descriptor(
  name='ResultProto',
  full_name='speckle.ResultProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='rows', full_name='speckle.ResultProto.rows', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='rows_updated', full_name='speckle.ResultProto.rows_updated', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='generated_keys', full_name='speckle.ResultProto.generated_keys', index=2,
      number=3, type=12, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='warnings', full_name='speckle.ResultProto.warnings', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='sql_exception', full_name='speckle.ResultProto.sql_exception', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='statement_id', full_name='speckle.ResultProto.statement_id', index=5,
      number=6, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='more_rows', full_name='speckle.ResultProto.more_rows', index=6,
      number=7, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='more_results', full_name='speckle.ResultProto.more_results', index=7,
      number=8, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='output_variable', full_name='speckle.ResultProto.output_variable', index=8,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='batch_rows_updated', full_name='speckle.ResultProto.batch_rows_updated', index=9,
      number=10, type=3, cpp_type=2, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='parameter_metadata', full_name='speckle.ResultProto.parameter_metadata', index=10,
      number=11, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=233,
  serialized_end=629,
)


_OPPROTO = _descriptor.Descriptor(
  name='OpProto',
  full_name='speckle.OpProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='type', full_name='speckle.OpProto.type', index=0,
      number=1, type=14, cpp_type=8, label=2,
      has_default_value=False, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='catalog', full_name='speckle.OpProto.catalog', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='sql', full_name='speckle.OpProto.sql', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='savepoint', full_name='speckle.OpProto.savepoint', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='auto_commit', full_name='speckle.OpProto.auto_commit', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='read_only', full_name='speckle.OpProto.read_only', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='transaction_isolation_level', full_name='speckle.OpProto.transaction_isolation_level', index=6,
      number=7, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='statement_id', full_name='speckle.OpProto.statement_id', index=7,
      number=8, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_id', full_name='speckle.OpProto.request_id', index=8,
      number=9, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _OPPROTO_OPTYPE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=632,
  serialized_end=1385,
)


_SAVEPOINT = _descriptor.Descriptor(
  name='SavePoint',
  full_name='speckle.SavePoint',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='speckle.SavePoint.id', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='name', full_name='speckle.SavePoint.name', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1387,
  serialized_end=1424,
)


_SQLEXCEPTION = _descriptor.Descriptor(
  name='SqlException',
  full_name='speckle.SqlException',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='message', full_name='speckle.SqlException.message', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='code', full_name='speckle.SqlException.code', index=1,
      number=2, type=5, cpp_type=1, label=2,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='sql_state', full_name='speckle.SqlException.sql_state', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='application_error_code', full_name='speckle.SqlException.application_error_code', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1426,
  serialized_end=1525,
)


_TUPLEPROTO = _descriptor.Descriptor(
  name='TupleProto',
  full_name='speckle.TupleProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='values', full_name='speckle.TupleProto.values', index=0,
      number=1, type=12, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nulls', full_name='speckle.TupleProto.nulls', index=1,
      number=2, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1527,
  serialized_end=1570,
)


_COLUMNPROTO = _descriptor.Descriptor(
  name='ColumnProto',
  full_name='speckle.ColumnProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='speckle.ColumnProto.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='label', full_name='speckle.ColumnProto.label', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type', full_name='speckle.ColumnProto.type', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=12,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='table_name', full_name='speckle.ColumnProto.table_name', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='schema_name', full_name='speckle.ColumnProto.schema_name', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='catalog_name', full_name='speckle.ColumnProto.catalog_name', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='precision', full_name='speckle.ColumnProto.precision', index=6,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='scale', full_name='speckle.ColumnProto.scale', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nullable', full_name='speckle.ColumnProto.nullable', index=8,
      number=9, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='searchable', full_name='speckle.ColumnProto.searchable', index=9,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='display_size', full_name='speckle.ColumnProto.display_size', index=10,
      number=11, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='auto_increment', full_name='speckle.ColumnProto.auto_increment', index=11,
      number=12, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='case_sensitive', full_name='speckle.ColumnProto.case_sensitive', index=12,
      number=13, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='currency', full_name='speckle.ColumnProto.currency', index=13,
      number=14, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='definitely_writable', full_name='speckle.ColumnProto.definitely_writable', index=14,
      number=15, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='read_only', full_name='speckle.ColumnProto.read_only', index=15,
      number=16, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='signed', full_name='speckle.ColumnProto.signed', index=16,
      number=17, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='writable', full_name='speckle.ColumnProto.writable', index=17,
      number=18, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='column_type_name', full_name='speckle.ColumnProto.column_type_name', index=18,
      number=19, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1573,
  serialized_end=2021,
)


_ROWSETPROTO = _descriptor.Descriptor(
  name='RowSetProto',
  full_name='speckle.RowSetProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='columns', full_name='speckle.RowSetProto.columns', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='tuples', full_name='speckle.RowSetProto.tuples', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2023,
  serialized_end=2112,
)


_JDBCDATABASEMETADATAPROTO_SCHEMA = _descriptor.Descriptor(
  name='Schema',
  full_name='speckle.JdbcDatabaseMetaDataProto.Schema',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='table_schema', full_name='speckle.JdbcDatabaseMetaDataProto.Schema.table_schema', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='table_catalog', full_name='speckle.JdbcDatabaseMetaDataProto.Schema.table_catalog', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8720,
  serialized_end=8773,
)

_JDBCDATABASEMETADATAPROTO = _descriptor.Descriptor(
  name='JdbcDatabaseMetaDataProto',
  full_name='speckle.JdbcDatabaseMetaDataProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='all_procedures_are_callable', full_name='speckle.JdbcDatabaseMetaDataProto.all_procedures_are_callable', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='all_tables_are_selectable', full_name='speckle.JdbcDatabaseMetaDataProto.all_tables_are_selectable', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='auto_commit_failure_closes_all_result_sets', full_name='speckle.JdbcDatabaseMetaDataProto.auto_commit_failure_closes_all_result_sets', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='data_definition_causes_transaction_commit', full_name='speckle.JdbcDatabaseMetaDataProto.data_definition_causes_transaction_commit', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='data_definition_ignored_in_transactions', full_name='speckle.JdbcDatabaseMetaDataProto.data_definition_ignored_in_transactions', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='does_max_row_size_include_blobs', full_name='speckle.JdbcDatabaseMetaDataProto.does_max_row_size_include_blobs', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='catalog_separator', full_name='speckle.JdbcDatabaseMetaDataProto.catalog_separator', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='catalog_term', full_name='speckle.JdbcDatabaseMetaDataProto.catalog_term', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='database_major_version', full_name='speckle.JdbcDatabaseMetaDataProto.database_major_version', index=8,
      number=9, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='database_minor_version', full_name='speckle.JdbcDatabaseMetaDataProto.database_minor_version', index=9,
      number=10, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='database_product_name', full_name='speckle.JdbcDatabaseMetaDataProto.database_product_name', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("Speckle", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='database_product_version', full_name='speckle.JdbcDatabaseMetaDataProto.database_product_version', index=11,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='default_transaction_isolation', full_name='speckle.JdbcDatabaseMetaDataProto.default_transaction_isolation', index=12,
      number=13, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='extra_name_characters', full_name='speckle.JdbcDatabaseMetaDataProto.extra_name_characters', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='identifier_quote_string', full_name='speckle.JdbcDatabaseMetaDataProto.identifier_quote_string', index=14,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jdbc_major_version', full_name='speckle.JdbcDatabaseMetaDataProto.jdbc_major_version', index=15,
      number=16, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jdbc_minor_version', full_name='speckle.JdbcDatabaseMetaDataProto.jdbc_minor_version', index=16,
      number=17, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_binary_literal_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_binary_literal_length', index=17,
      number=18, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_catalog_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_catalog_name_length', index=18,
      number=19, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_char_literal_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_char_literal_length', index=19,
      number=20, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_column_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_column_name_length', index=20,
      number=21, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_columns_in_group_by', full_name='speckle.JdbcDatabaseMetaDataProto.max_columns_in_group_by', index=21,
      number=22, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_columns_in_index', full_name='speckle.JdbcDatabaseMetaDataProto.max_columns_in_index', index=22,
      number=23, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_columns_in_order_by', full_name='speckle.JdbcDatabaseMetaDataProto.max_columns_in_order_by', index=23,
      number=24, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_columns_in_select', full_name='speckle.JdbcDatabaseMetaDataProto.max_columns_in_select', index=24,
      number=25, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_columns_in_table', full_name='speckle.JdbcDatabaseMetaDataProto.max_columns_in_table', index=25,
      number=26, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_connections', full_name='speckle.JdbcDatabaseMetaDataProto.max_connections', index=26,
      number=27, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_cursor_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_cursor_name_length', index=27,
      number=28, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_index_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_index_length', index=28,
      number=29, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_procedure_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_procedure_name_length', index=29,
      number=30, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_row_size', full_name='speckle.JdbcDatabaseMetaDataProto.max_row_size', index=30,
      number=31, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_schema_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_schema_name_length', index=31,
      number=32, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_statement_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_statement_length', index=32,
      number=33, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_statements', full_name='speckle.JdbcDatabaseMetaDataProto.max_statements', index=33,
      number=34, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_table_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_table_name_length', index=34,
      number=35, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_tables_in_select', full_name='speckle.JdbcDatabaseMetaDataProto.max_tables_in_select', index=35,
      number=36, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_user_name_length', full_name='speckle.JdbcDatabaseMetaDataProto.max_user_name_length', index=36,
      number=37, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='numeric_functions', full_name='speckle.JdbcDatabaseMetaDataProto.numeric_functions', index=37,
      number=38, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='procedure_term', full_name='speckle.JdbcDatabaseMetaDataProto.procedure_term', index=38,
      number=39, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='resultset_holdability', full_name='speckle.JdbcDatabaseMetaDataProto.resultset_holdability', index=39,
      number=40, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=2,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='rowid_lifetime', full_name='speckle.JdbcDatabaseMetaDataProto.rowid_lifetime', index=40,
      number=41, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='sql_keywords', full_name='speckle.JdbcDatabaseMetaDataProto.sql_keywords', index=41,
      number=42, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='sql_state_type', full_name='speckle.JdbcDatabaseMetaDataProto.sql_state_type', index=42,
      number=43, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='schema_term', full_name='speckle.JdbcDatabaseMetaDataProto.schema_term', index=43,
      number=44, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='search_string_escape', full_name='speckle.JdbcDatabaseMetaDataProto.search_string_escape', index=44,
      number=45, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='string_functions', full_name='speckle.JdbcDatabaseMetaDataProto.string_functions', index=45,
      number=46, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='system_functions', full_name='speckle.JdbcDatabaseMetaDataProto.system_functions', index=46,
      number=47, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='time_date_functions', full_name='speckle.JdbcDatabaseMetaDataProto.time_date_functions', index=47,
      number=48, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='user_name', full_name='speckle.JdbcDatabaseMetaDataProto.user_name', index=48,
      number=49, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='catalog_at_start', full_name='speckle.JdbcDatabaseMetaDataProto.catalog_at_start', index=49,
      number=50, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='locators_update_copy', full_name='speckle.JdbcDatabaseMetaDataProto.locators_update_copy', index=50,
      number=51, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='null_plus_non_null_is_null', full_name='speckle.JdbcDatabaseMetaDataProto.null_plus_non_null_is_null', index=51,
      number=52, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nulls_are_sorted_at_end', full_name='speckle.JdbcDatabaseMetaDataProto.nulls_are_sorted_at_end', index=52,
      number=53, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nulls_are_sorted_at_start', full_name='speckle.JdbcDatabaseMetaDataProto.nulls_are_sorted_at_start', index=53,
      number=54, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nulls_are_sorted_high', full_name='speckle.JdbcDatabaseMetaDataProto.nulls_are_sorted_high', index=54,
      number=55, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nulls_are_sorted_low', full_name='speckle.JdbcDatabaseMetaDataProto.nulls_are_sorted_low', index=55,
      number=56, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stores_lower_case_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.stores_lower_case_identifiers', index=56,
      number=57, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stores_lower_case_quoted_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.stores_lower_case_quoted_identifiers', index=57,
      number=58, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stores_mixed_case_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.stores_mixed_case_identifiers', index=58,
      number=59, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stores_mixed_case_quoted_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.stores_mixed_case_quoted_identifiers', index=59,
      number=60, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stores_upper_case_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.stores_upper_case_identifiers', index=60,
      number=61, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stores_upper_case_quoted_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.stores_upper_case_quoted_identifiers', index=61,
      number=62, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_ansi92_entry_level_sql', full_name='speckle.JdbcDatabaseMetaDataProto.supports_ansi92_entry_level_sql', index=62,
      number=63, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_ansi92_full_sql', full_name='speckle.JdbcDatabaseMetaDataProto.supports_ansi92_full_sql', index=63,
      number=64, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_ansi92_intermediate_sql', full_name='speckle.JdbcDatabaseMetaDataProto.supports_ansi92_intermediate_sql', index=64,
      number=65, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_alter_table_with_add_column', full_name='speckle.JdbcDatabaseMetaDataProto.supports_alter_table_with_add_column', index=65,
      number=66, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_alter_table_with_drop_column', full_name='speckle.JdbcDatabaseMetaDataProto.supports_alter_table_with_drop_column', index=66,
      number=67, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_batch_updates', full_name='speckle.JdbcDatabaseMetaDataProto.supports_batch_updates', index=67,
      number=68, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_catalogs_in_data_manipulation', full_name='speckle.JdbcDatabaseMetaDataProto.supports_catalogs_in_data_manipulation', index=68,
      number=69, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_catalogs_in_index_definitions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_catalogs_in_index_definitions', index=69,
      number=70, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_catalogs_in_privilege_definitions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_catalogs_in_privilege_definitions', index=70,
      number=71, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_catalogs_in_procedure_calls', full_name='speckle.JdbcDatabaseMetaDataProto.supports_catalogs_in_procedure_calls', index=71,
      number=72, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_catalogs_in_table_definitions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_catalogs_in_table_definitions', index=72,
      number=73, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_column_aliasing', full_name='speckle.JdbcDatabaseMetaDataProto.supports_column_aliasing', index=73,
      number=74, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_convert', full_name='speckle.JdbcDatabaseMetaDataProto.supports_convert', index=74,
      number=75, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_core_sql_grammar', full_name='speckle.JdbcDatabaseMetaDataProto.supports_core_sql_grammar', index=75,
      number=76, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_correlated_subqueries', full_name='speckle.JdbcDatabaseMetaDataProto.supports_correlated_subqueries', index=76,
      number=77, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_data_definition_and_data_manipulation_transactions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_data_definition_and_data_manipulation_transactions', index=77,
      number=78, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_data_manipulation_transactions_only', full_name='speckle.JdbcDatabaseMetaDataProto.supports_data_manipulation_transactions_only', index=78,
      number=79, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_different_table_correlation_names', full_name='speckle.JdbcDatabaseMetaDataProto.supports_different_table_correlation_names', index=79,
      number=80, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_expressions_in_order_by', full_name='speckle.JdbcDatabaseMetaDataProto.supports_expressions_in_order_by', index=80,
      number=81, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_extended_sql_grammar', full_name='speckle.JdbcDatabaseMetaDataProto.supports_extended_sql_grammar', index=81,
      number=82, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_full_outer_joins', full_name='speckle.JdbcDatabaseMetaDataProto.supports_full_outer_joins', index=82,
      number=83, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_get_generated_keys', full_name='speckle.JdbcDatabaseMetaDataProto.supports_get_generated_keys', index=83,
      number=84, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_group_by', full_name='speckle.JdbcDatabaseMetaDataProto.supports_group_by', index=84,
      number=85, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_group_by_beyond_select', full_name='speckle.JdbcDatabaseMetaDataProto.supports_group_by_beyond_select', index=85,
      number=86, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_group_by_unrelated', full_name='speckle.JdbcDatabaseMetaDataProto.supports_group_by_unrelated', index=86,
      number=87, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_integrity_enhancement_facility', full_name='speckle.JdbcDatabaseMetaDataProto.supports_integrity_enhancement_facility', index=87,
      number=88, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_like_escape_clause', full_name='speckle.JdbcDatabaseMetaDataProto.supports_like_escape_clause', index=88,
      number=89, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_limited_outer_joins', full_name='speckle.JdbcDatabaseMetaDataProto.supports_limited_outer_joins', index=89,
      number=90, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_minimum_sql_grammar', full_name='speckle.JdbcDatabaseMetaDataProto.supports_minimum_sql_grammar', index=90,
      number=91, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_mixed_case_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.supports_mixed_case_identifiers', index=91,
      number=92, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_mixed_case_quoted_identifiers', full_name='speckle.JdbcDatabaseMetaDataProto.supports_mixed_case_quoted_identifiers', index=92,
      number=93, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_multiple_open_results', full_name='speckle.JdbcDatabaseMetaDataProto.supports_multiple_open_results', index=93,
      number=94, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_multiple_result_sets', full_name='speckle.JdbcDatabaseMetaDataProto.supports_multiple_result_sets', index=94,
      number=95, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_multiple_transactions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_multiple_transactions', index=95,
      number=96, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_named_parameters', full_name='speckle.JdbcDatabaseMetaDataProto.supports_named_parameters', index=96,
      number=97, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_non_nullable_columns', full_name='speckle.JdbcDatabaseMetaDataProto.supports_non_nullable_columns', index=97,
      number=98, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_open_cursors_across_commit', full_name='speckle.JdbcDatabaseMetaDataProto.supports_open_cursors_across_commit', index=98,
      number=99, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_open_cursors_across_rollback', full_name='speckle.JdbcDatabaseMetaDataProto.supports_open_cursors_across_rollback', index=99,
      number=100, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_open_statements_across_commit', full_name='speckle.JdbcDatabaseMetaDataProto.supports_open_statements_across_commit', index=100,
      number=101, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_open_statements_across_rollback', full_name='speckle.JdbcDatabaseMetaDataProto.supports_open_statements_across_rollback', index=101,
      number=102, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_order_by_unrelated', full_name='speckle.JdbcDatabaseMetaDataProto.supports_order_by_unrelated', index=102,
      number=103, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_outer_joins', full_name='speckle.JdbcDatabaseMetaDataProto.supports_outer_joins', index=103,
      number=104, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_positioned_delete', full_name='speckle.JdbcDatabaseMetaDataProto.supports_positioned_delete', index=104,
      number=105, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_positioned_update', full_name='speckle.JdbcDatabaseMetaDataProto.supports_positioned_update', index=105,
      number=106, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_savepoints', full_name='speckle.JdbcDatabaseMetaDataProto.supports_savepoints', index=106,
      number=107, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_schemas_in_data_manipulation', full_name='speckle.JdbcDatabaseMetaDataProto.supports_schemas_in_data_manipulation', index=107,
      number=108, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_schemas_in_index_definitions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_schemas_in_index_definitions', index=108,
      number=109, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_schemas_in_privilege_definitions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_schemas_in_privilege_definitions', index=109,
      number=110, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_schemas_in_procedure_calls', full_name='speckle.JdbcDatabaseMetaDataProto.supports_schemas_in_procedure_calls', index=110,
      number=111, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_schemas_in_table_definitions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_schemas_in_table_definitions', index=111,
      number=112, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_select_for_update', full_name='speckle.JdbcDatabaseMetaDataProto.supports_select_for_update', index=112,
      number=113, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_statement_pooling', full_name='speckle.JdbcDatabaseMetaDataProto.supports_statement_pooling', index=113,
      number=114, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_stored_functions_using_call_syntax', full_name='speckle.JdbcDatabaseMetaDataProto.supports_stored_functions_using_call_syntax', index=114,
      number=115, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_stored_procedures', full_name='speckle.JdbcDatabaseMetaDataProto.supports_stored_procedures', index=115,
      number=116, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_subqueries_in_comparisons', full_name='speckle.JdbcDatabaseMetaDataProto.supports_subqueries_in_comparisons', index=116,
      number=117, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_subqueries_in_exists', full_name='speckle.JdbcDatabaseMetaDataProto.supports_subqueries_in_exists', index=117,
      number=118, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_subqueries_in_ins', full_name='speckle.JdbcDatabaseMetaDataProto.supports_subqueries_in_ins', index=118,
      number=119, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_subqueries_in_quantifieds', full_name='speckle.JdbcDatabaseMetaDataProto.supports_subqueries_in_quantifieds', index=119,
      number=120, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_table_correlation_names', full_name='speckle.JdbcDatabaseMetaDataProto.supports_table_correlation_names', index=120,
      number=121, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_transactions', full_name='speckle.JdbcDatabaseMetaDataProto.supports_transactions', index=121,
      number=122, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_union', full_name='speckle.JdbcDatabaseMetaDataProto.supports_union', index=122,
      number=123, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_union_all', full_name='speckle.JdbcDatabaseMetaDataProto.supports_union_all', index=123,
      number=124, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uses_local_file_per_table', full_name='speckle.JdbcDatabaseMetaDataProto.uses_local_file_per_table', index=124,
      number=125, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uses_local_files', full_name='speckle.JdbcDatabaseMetaDataProto.uses_local_files', index=125,
      number=126, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='read_only', full_name='speckle.JdbcDatabaseMetaDataProto.read_only', index=126,
      number=127, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='table_types', full_name='speckle.JdbcDatabaseMetaDataProto.table_types', index=127,
      number=128, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='catalogs', full_name='speckle.JdbcDatabaseMetaDataProto.catalogs', index=128,
      number=129, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='schemas', full_name='speckle.JdbcDatabaseMetaDataProto.schemas', index=129,
      number=130, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deletes_are_detected', full_name='speckle.JdbcDatabaseMetaDataProto.deletes_are_detected', index=130,
      number=131, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='inserts_are_detected', full_name='speckle.JdbcDatabaseMetaDataProto.inserts_are_detected', index=131,
      number=132, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='updates_are_detected', full_name='speckle.JdbcDatabaseMetaDataProto.updates_are_detected', index=132,
      number=133, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='others_deletes_are_visible', full_name='speckle.JdbcDatabaseMetaDataProto.others_deletes_are_visible', index=133,
      number=134, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='others_inserts_are_visible', full_name='speckle.JdbcDatabaseMetaDataProto.others_inserts_are_visible', index=134,
      number=135, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='others_updates_are_visible', full_name='speckle.JdbcDatabaseMetaDataProto.others_updates_are_visible', index=135,
      number=136, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='own_deletes_are_visible', full_name='speckle.JdbcDatabaseMetaDataProto.own_deletes_are_visible', index=136,
      number=137, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='own_inserts_are_visible', full_name='speckle.JdbcDatabaseMetaDataProto.own_inserts_are_visible', index=137,
      number=138, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='own_updates_are_visible', full_name='speckle.JdbcDatabaseMetaDataProto.own_updates_are_visible', index=138,
      number=139, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_result_set_concurrency_updatable', full_name='speckle.JdbcDatabaseMetaDataProto.supports_result_set_concurrency_updatable', index=139,
      number=140, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_result_set_type', full_name='speckle.JdbcDatabaseMetaDataProto.supports_result_set_type', index=140,
      number=141, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_result_set_holdability', full_name='speckle.JdbcDatabaseMetaDataProto.supports_result_set_holdability', index=141,
      number=142, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='supports_transaction_isolation_level', full_name='speckle.JdbcDatabaseMetaDataProto.supports_transaction_isolation_level', index=142,
      number=143, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='generated_key_always_returned', full_name='speckle.JdbcDatabaseMetaDataProto.generated_key_always_returned', index=143,
      number=144, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_JDBCDATABASEMETADATAPROTO_SCHEMA, ],
  enum_types=[
    _JDBCDATABASEMETADATAPROTO_ROWIDLIFETIME,
    _JDBCDATABASEMETADATAPROTO_SQLSTATETYPE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2115,
  serialized_end=9102,
)


_PROPERTY = _descriptor.Descriptor(
  name='Property',
  full_name='speckle.Property',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='key', full_name='speckle.Property.key', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='value', full_name='speckle.Property.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9104,
  serialized_end=9142,
)


_EXECOPTIONS = _descriptor.Descriptor(
  name='ExecOptions',
  full_name='speckle.ExecOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='include_generated_keys', full_name='speckle.ExecOptions.include_generated_keys', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='generated_column_indices', full_name='speckle.ExecOptions.generated_column_indices', index=1,
      number=2, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='generated_column_names', full_name='speckle.ExecOptions.generated_column_names', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type', full_name='speckle.ExecOptions.type', index=3,
      number=4, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=1003,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='concurrency', full_name='speckle.ExecOptions.concurrency', index=4,
      number=5, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=1007,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='holdability', full_name='speckle.ExecOptions.holdability', index=5,
      number=6, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fetch_size', full_name='speckle.ExecOptions.fetch_size', index=6,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_rows', full_name='speckle.ExecOptions.max_rows', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='poolable', full_name='speckle.ExecOptions.poolable', index=8,
      number=9, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fetch_direction', full_name='speckle.ExecOptions.fetch_direction', index=9,
      number=10, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=1000,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cursor_name', full_name='speckle.ExecOptions.cursor_name', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='max_field_size', full_name='speckle.ExecOptions.max_field_size', index=11,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='escape_processing', full_name='speckle.ExecOptions.escape_processing', index=12,
      number=13, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9145,
  serialized_end=9615,
)


_BATCHBINDVARIABLEPROTO = _descriptor.Descriptor(
  name='BatchBindVariableProto',
  full_name='speckle.BatchBindVariableProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bind_variable', full_name='speckle.BatchBindVariableProto.bind_variable', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9617,
  serialized_end=9692,
)


_BATCHPROTO = _descriptor.Descriptor(
  name='BatchProto',
  full_name='speckle.BatchProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='statement', full_name='speckle.BatchProto.statement', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='batch_bind_variable', full_name='speckle.BatchProto.batch_bind_variable', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9694,
  serialized_end=9787,
)


_PARAMETERMETADATA = _descriptor.Descriptor(
  name='ParameterMetadata',
  full_name='speckle.ParameterMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='speckle.ParameterMetadata.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9789,
  serialized_end=9822,
)


_RPCERRORPROTO = _descriptor.Descriptor(
  name='RpcErrorProto',
  full_name='speckle.RpcErrorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='error_code', full_name='speckle.RpcErrorProto.error_code', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='error_message', full_name='speckle.RpcErrorProto.error_message', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9824,
  serialized_end=9882,
)

_BINDVARIABLEPROTO.fields_by_name['direction'].enum_type = _BINDVARIABLEPROTO_DIRECTION
_BINDVARIABLEPROTO_DIRECTION.containing_type = _BINDVARIABLEPROTO;
_RESULTPROTO.fields_by_name['rows'].message_type = _ROWSETPROTO
_RESULTPROTO.fields_by_name['warnings'].message_type = _SQLEXCEPTION
_RESULTPROTO.fields_by_name['sql_exception'].message_type = _SQLEXCEPTION
_RESULTPROTO.fields_by_name['output_variable'].message_type = _BINDVARIABLEPROTO
_RESULTPROTO.fields_by_name['parameter_metadata'].message_type = _PARAMETERMETADATA
_OPPROTO.fields_by_name['type'].enum_type = _OPPROTO_OPTYPE
_OPPROTO.fields_by_name['savepoint'].message_type = _SAVEPOINT
_OPPROTO.fields_by_name['transaction_isolation_level'].enum_type = _TRANSACTIONISOLATIONLEVEL
_OPPROTO_OPTYPE.containing_type = _OPPROTO;
_ROWSETPROTO.fields_by_name['columns'].message_type = _COLUMNPROTO
_ROWSETPROTO.fields_by_name['tuples'].message_type = _TUPLEPROTO
_JDBCDATABASEMETADATAPROTO_SCHEMA.containing_type = _JDBCDATABASEMETADATAPROTO;
_JDBCDATABASEMETADATAPROTO.fields_by_name['default_transaction_isolation'].enum_type = _TRANSACTIONISOLATIONLEVEL
_JDBCDATABASEMETADATAPROTO.fields_by_name['resultset_holdability'].enum_type = _RESULTSETHOLDABILITY
_JDBCDATABASEMETADATAPROTO.fields_by_name['rowid_lifetime'].enum_type = _JDBCDATABASEMETADATAPROTO_ROWIDLIFETIME
_JDBCDATABASEMETADATAPROTO.fields_by_name['sql_state_type'].enum_type = _JDBCDATABASEMETADATAPROTO_SQLSTATETYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['schemas'].message_type = _JDBCDATABASEMETADATAPROTO_SCHEMA
_JDBCDATABASEMETADATAPROTO.fields_by_name['deletes_are_detected'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['inserts_are_detected'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['updates_are_detected'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['others_deletes_are_visible'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['others_inserts_are_visible'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['others_updates_are_visible'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['own_deletes_are_visible'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['own_inserts_are_visible'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['own_updates_are_visible'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['supports_result_set_concurrency_updatable'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['supports_result_set_type'].enum_type = _RESULTSETTYPE
_JDBCDATABASEMETADATAPROTO.fields_by_name['supports_result_set_holdability'].enum_type = _RESULTSETHOLDABILITY
_JDBCDATABASEMETADATAPROTO.fields_by_name['supports_transaction_isolation_level'].enum_type = _TRANSACTIONISOLATIONLEVEL
_JDBCDATABASEMETADATAPROTO_ROWIDLIFETIME.containing_type = _JDBCDATABASEMETADATAPROTO;
_JDBCDATABASEMETADATAPROTO_SQLSTATETYPE.containing_type = _JDBCDATABASEMETADATAPROTO;
_EXECOPTIONS.fields_by_name['type'].enum_type = _RESULTSETTYPE
_EXECOPTIONS.fields_by_name['concurrency'].enum_type = _RESULTSETCONCURRENCY
_EXECOPTIONS.fields_by_name['holdability'].enum_type = _RESULTSETHOLDABILITY
_EXECOPTIONS.fields_by_name['fetch_direction'].enum_type = _FETCHDIRECTION
_BATCHBINDVARIABLEPROTO.fields_by_name['bind_variable'].message_type = _BINDVARIABLEPROTO
_BATCHPROTO.fields_by_name['batch_bind_variable'].message_type = _BATCHBINDVARIABLEPROTO
DESCRIPTOR.message_types_by_name['BindVariableProto'] = _BINDVARIABLEPROTO
DESCRIPTOR.message_types_by_name['ResultProto'] = _RESULTPROTO
DESCRIPTOR.message_types_by_name['OpProto'] = _OPPROTO
DESCRIPTOR.message_types_by_name['SavePoint'] = _SAVEPOINT
DESCRIPTOR.message_types_by_name['SqlException'] = _SQLEXCEPTION
DESCRIPTOR.message_types_by_name['TupleProto'] = _TUPLEPROTO
DESCRIPTOR.message_types_by_name['ColumnProto'] = _COLUMNPROTO
DESCRIPTOR.message_types_by_name['RowSetProto'] = _ROWSETPROTO
DESCRIPTOR.message_types_by_name['JdbcDatabaseMetaDataProto'] = _JDBCDATABASEMETADATAPROTO
DESCRIPTOR.message_types_by_name['Property'] = _PROPERTY
DESCRIPTOR.message_types_by_name['ExecOptions'] = _EXECOPTIONS
DESCRIPTOR.message_types_by_name['BatchBindVariableProto'] = _BATCHBINDVARIABLEPROTO
DESCRIPTOR.message_types_by_name['BatchProto'] = _BATCHPROTO
DESCRIPTOR.message_types_by_name['ParameterMetadata'] = _PARAMETERMETADATA
DESCRIPTOR.message_types_by_name['RpcErrorProto'] = _RPCERRORPROTO

class BindVariableProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BINDVARIABLEPROTO



class ResultProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESULTPROTO



class OpProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _OPPROTO



class SavePoint(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SAVEPOINT



class SqlException(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SQLEXCEPTION



class TupleProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TUPLEPROTO



class ColumnProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _COLUMNPROTO



class RowSetProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ROWSETPROTO



class JdbcDatabaseMetaDataProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class Schema(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _JDBCDATABASEMETADATAPROTO_SCHEMA


  DESCRIPTOR = _JDBCDATABASEMETADATAPROTO



class Property(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PROPERTY



class ExecOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXECOPTIONS



class BatchBindVariableProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BATCHBINDVARIABLEPROTO



class BatchProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BATCHPROTO



class ParameterMetadata(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PARAMETERMETADATA



class RpcErrorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RPCERRORPROTO




DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(descriptor_pb2.FileOptions(), '\n\033com.google.protos.cloud.sql\020\002 \002(\002xd')

