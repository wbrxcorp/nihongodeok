package com.nihongodeok.api

import org.springframework.beans.factory.annotation.Autowired
import javax.sql.DataSource
import scala.collection.JavaConversions._

class Row(row:java.util.Map[String,AnyRef]) {
  val this.row = row
  def apply[A](col:String)(implicit m:ClassManifest[A]):A = {
    val anyref = row.get(col)
    if (anyref.isInstanceOf[Long] && m.erasure == classOf[Int]) {
      return anyref.asInstanceOf[Long].toInt.asInstanceOf[A]
    }
    anyref.asInstanceOf[A]
  }
  
  def option[A](col:String):Option[A] = {
    Option(row.get(col).asInstanceOf[A])
  }
}

class JdbcTemplate(dataSource:DataSource) {
  val jdbcTemplate = new org.springframework.jdbc.core.JdbcTemplate(dataSource)

	def toJavaObjectSeq(args:Any*):Seq[Object] = {
	  args.map { x=>
	    if (x == None || x == null) {
	      null
	    } else if (x.isInstanceOf[Some[Boolean]]){
	    	x.asInstanceOf[Some[Boolean]].get.asInstanceOf[Object]
	    } else if (x.isInstanceOf[Some[String]]) {
	    	x.asInstanceOf[Some[String]].get.asInstanceOf[Object]
	    } else if (x.isInstanceOf[Some[Int]]) {
	    	x.asInstanceOf[Some[Int]].get.asInstanceOf[Object]
	    } else if (x.isInstanceOf[Some[Long]]) {
	    	x.asInstanceOf[Some[Long]].get.asInstanceOf[Object]
	    } else {
	    	x.asInstanceOf[Object]
	    }
	  }
	}

  def queryForSeq(sql:String, args:Any*):Seq[Row] =
  	jdbcTemplate.queryForList(sql, toJavaObjectSeq(args):_*).map { x=> new Row(x) }

  def queryForString(sql:String, args:Any*):String = 
	jdbcTemplate.queryForList(sql, classOf[String], toJavaObjectSeq(args):_*).head

  def queryForStringOption(sql:String, args:Any*):Option[String] = 
	jdbcTemplate.queryForList(sql, classOf[String], toJavaObjectSeq(args):_*).headOption
	
  def queryForInt(sql:String, args:Any*):Int = 
    jdbcTemplate.queryForList(sql, classOf[java.lang.Long], toJavaObjectSeq(args):_*).headOption match {
    case Some(v) => v.toInt
    case None => 0
    }

  def queryForIntOption(sql:String, args:Any*):Option[Int] = 
    jdbcTemplate.queryForList(sql, classOf[java.lang.Long], toJavaObjectSeq(args):_*).headOption.map(_.toInt)
  
  def update(sql:String, args:Any*):Int = 
	jdbcTemplate.update(sql, toJavaObjectSeq(args):_*)
}

trait DataSourceSupport {
	@Autowired private var dataSource:DataSource = _

	def jdbcTemplate() = new JdbcTemplate(dataSource)
	
	/*
	*/
}
