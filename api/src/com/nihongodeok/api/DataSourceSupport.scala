package com.nihongodeok.api

import org.springframework.beans.factory.annotation.Autowired
import javax.sql.DataSource
import org.springframework.jdbc.core.JdbcTemplate

trait DataSourceSupport {
	@Autowired private var dataSource:DataSource = _

	def jdbcTemplate() = new JdbcTemplate(dataSource)
}
