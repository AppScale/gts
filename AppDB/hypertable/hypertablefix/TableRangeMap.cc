#include <Common/Compat.h>
#include "TableRangeMap.h"
#include <iostream>

namespace Mapreduce
{
  TableRangeMap::TableRangeMap(const std::string TableName,
      const std::string RootPath)
  {
    m_client = new Client(RootPath);

    m_user_table = m_client->open_table(TableName);
    m_meta_table = m_client->open_table("METADATA");

    m_user_table->get_identifier(&m_table_id);
  }

  std::vector<RangeLocationInfo> *TableRangeMap::getMap()
  {
    char tmprow[16];
    std::string endrow, startrow;
    ScanSpecBuilder meta_scan_builder;
    TableScannerPtr scanner;
    std::vector<RangeLocationInfo> *range_vector;
    Cell cell;

    snprintf(tmprow, 16, "%u:", m_table_id.id);

    startrow = tmprow;

    meta_scan_builder.add_row_interval(startrow.c_str(), true, (startrow + "\xff\xff").c_str(), true);

    /* select columns */
    meta_scan_builder.add_column("StartRow");
    meta_scan_builder.add_column("Location");

    scanner = m_meta_table->create_scanner(meta_scan_builder.get());

    range_vector = new std::vector<RangeLocationInfo>();
    while (scanner->next(cell))
    {
      RangeLocationInfo range;
      char *v;
      /*
         the first cell is a StartRow and the start of the range
         is encoded within the cell value, so extract it first.
         */
      v = new char[cell.value_len + 1];
      memcpy(v, cell.value, cell.value_len);
      v[cell.value_len] = 0;
      range.start_row = std::string(v);
      delete v;
      v = NULL;

      /*
         the last row of the range (not inclusive) is encoded within the row key
         so extract it next

         note below: I rely on the assumption that
         the row key is 0 terminated. the below code will
         cause problems otherwise
         */
      range.end_row = std::string(cell.row_key+2);

      /* the second cell is Location */
      scanner->next(cell);

      v = new char[cell.value_len+1];
      memcpy(v, cell.value, cell.value_len);
      v[cell.value_len] = 0;
      range.location = std::string(v);
      delete v;
      v = NULL;

      range_vector->push_back(range);
    }

    return range_vector;
  }
}

