#include "TableReader.h"
#include <iostream>

namespace Mapreduce {
TableReader::TableReader(HadoopPipes::MapContext& context)
{
  const HadoopPipes::JobConf *job = context.getJobConf();
  std::string tableName = job->get("hypertable.table.name");
  std::string rootPath = job->get("hypertable.root.path");
  bool allColumns = job->getBoolean("hypertable.table.columns.all");

  m_client = new Client(rootPath);

  m_table = m_client->open_table(tableName);

  ScanSpecBuilder scan_spec_builder;

  std::string start_row;
  std::string end_row;
  std::string tablename;

  HadoopUtils::StringInStream stream(context.getInputSplit());
  HadoopUtils::deserializeString(tablename, stream);
  HadoopUtils::deserializeString(start_row, stream);
  HadoopUtils::deserializeString(end_row, stream);

  scan_spec_builder.add_row_interval(start_row.c_str(), true, end_row.c_str(), true);

  if (allColumns == false) {
    std::vector<std::string> columns;
    using namespace boost::algorithm;

    split(columns, job->get("hypertable.table.columns"), is_any_of(", "));
    BOOST_FOREACH(const std::string &c, columns) {
      scan_spec_builder.add_column(c.c_str());
    }
  }
  m_scanner = m_table->create_scanner(scan_spec_builder.get());
}

TableReader::~TableReader()
{
}

bool TableReader::next(std::string& key, std::string& value) {
  Cell cell;

  if (m_scanner->next(cell)) {
    std::string key_composition;

    key_composition = cell.row_key;
    key_composition.append(":");
    key_composition.append(cell.column_family);
    key_composition.append(":");
    key_composition.append(cell.column_qualifier);

    key = key_composition;

    char *s = new char[cell.value_len+1];
    memcpy(s, cell.value, cell.value_len);
    s[cell.value_len] = 0;
    value = s;
    delete s;

    return true;
  } else {
    return false;
  }
}

}

