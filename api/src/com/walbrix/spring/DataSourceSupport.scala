package com.walbrix.spring

import org.springframework.beans.factory.annotation.Autowired
import javax.sql.DataSource
import scala.collection.JavaConversions._
import java.math.BigInteger
import java.sql.Timestamp

class Row(row:java.util.Map[String,AnyRef]) {
  val this.row = row

  type DI = DummyImplicit
  
  def getColumn(col:String):AnyRef = {
    assert(row.containsKey(col))
    row.get(col)
  }

  def apply(col:String)(implicit d1:DI):Int = {
	  getColumn(col) match {
	      case null => 0
	      case x:Number => x.asInstanceOf[Number].intValue()
	      case y:String => y.toInt
	  }
  }

  def apply(col:String)(implicit d1:DI,d2:DI):Option[Int] = {
	  getColumn(col) match {
	      case null => None
	      case x:Number => Some(x.asInstanceOf[Number].intValue())
	      case y:String => Some(y.toInt)
	  }
  }
  
  def apply(col:String)(implicit d1:DI,d2:DI,d3:DI):String = {
	  getColumn(col) match {
	      case null => null
	      case x:String => x
	      case y => y.toString()
	  }
  }
  
  def apply(col:String)
  	(implicit d1:DummyImplicit,d2:DI,d3:DI,d4:DI)
  	:Option[String] = {
	  getColumn(col) match {
	      case null => None
	      case x:String => Some(x)
	      case y => Some(y.toString())
	  }
  }

  def apply(col:String)
  	(implicit d1:DI,d2:DI,d3:DI,d4:DI,d5:DI):Timestamp = {
	  getColumn(col) match {
	      case null => null
	      case x:Timestamp => x
	      case y => assert(false); null
	  }
  }
  
  def apply(col:String)
  	(implicit d1:DI,d2:DI,d3:DI,d4:DI,d5:DI,d6:DI):Option[Timestamp] = {
	  getColumn(col) match {
	      case null => None
	      case x:Timestamp => Some(x)
	      case y => assert(false); None
	  }
  }
  
  def apply(col:String)
  	(implicit d1:DI,d2:DI,d3:DI,d4:DI,d5:DI,d6:DI,d7:DI):Boolean = {
	  getColumn(col) match {
	      case null => false
	      case x:java.lang.Boolean => x
	      case y:Number => y.longValue() != 0
	  }
  }

  def apply(col:String)
  	(implicit d1:DI,d2:DI,d3:DI,d4:DI,d5:DI,d6:DI,d7:DI,d8:DI,d9:DI)
  	:Option[java.math.BigDecimal] = {
      val value = row.get(col)
	  value match {
	      case null => None
	      case y:java.math.BigDecimal => Some(y)
	      case x:String => Some(new java.math.BigDecimal(x))
	      case z:java.lang.Long => Some(java.math.BigDecimal.valueOf(z))
	      case w:java.lang.Double => Some(java.math.BigDecimal.valueOf(w))
	      case _ => assert(false); None
	  }
  }

  def apply(col:String)
  	(implicit d1:DI,d2:DI,d3:DI,d4:DI,d5:DI,d6:DI,d7:DI,d8:DI,d9:DI,d10:DI)
  	:java.math.BigDecimal = {
      val value = row.get(col)
	  value match {
	      case null => null
	      case y:java.math.BigDecimal => y
	      case x:String => new java.math.BigDecimal(x)
	      case z:java.lang.Long => java.math.BigDecimal.valueOf(z)
	      case w:java.lang.Double => java.math.BigDecimal.valueOf(w)
	      case _ => assert(false); null
	  }
  }

  def apply(col:String)
  	(implicit d1:DI,d2:DI,d3:DI,d4:DI,d5:DI,d6:DI,d7:DI,d8:DI,d9:DI,d10:DI,d11:DI)
  	:Array[Byte] = {
      val value = row.get(col)
	  value match {
	      case null => null
	      case y:Array[Byte] => y
	      case _ => assert(false); null
	  }
  }
}

class JdbcTemplate(dataSource:DataSource) {
  val jdbcTemplate = new org.springframework.jdbc.core.JdbcTemplate(dataSource)

	def toJavaObjectSeq(args:Any*):Seq[Object] = args.map { x=>
	    if (x == None || x == null) {
	      null
	    } else if (x.isInstanceOf[Some[Any]]){
	    	x.asInstanceOf[Some[Any]].get.asInstanceOf[Object]
	    } else {
	    	x.asInstanceOf[Object]
	    }
	}

  def queryForSingleRow(sql:String, args:Any*):Option[Row] = {
  	jdbcTemplate.queryForList(sql, toJavaObjectSeq(args:_*):_*).headOption match {
  	  case None => None
  	  case Some(x:java.util.Map[String,AnyRef]) => Some(new Row(x))
  	}
  }
  
  def queryForSeq(sql:String, args:Any*):Seq[Row] =
  	jdbcTemplate.queryForList(sql, toJavaObjectSeq(args:_*):_*).map { x=> new Row(x) }

  def queryForString(sql:String, args:Any*):String = 
	jdbcTemplate.queryForList(sql, classOf[String], toJavaObjectSeq(args:_*):_*).head

  def queryForStringOption(sql:String, args:Any*):Option[String] = 
	jdbcTemplate.queryForList(sql, classOf[String], toJavaObjectSeq(args:_*):_*).headOption
	
  def queryForInt(sql:String, args:Any*):Int = 
    jdbcTemplate.queryForList(sql, classOf[java.lang.Long], toJavaObjectSeq(args:_*):_*).headOption match {
	    case Some(v) => v.toInt
	    case None => 0
    }

  def queryForInt(sql:String, args:Any*)(implicit di1:DummyImplicit):Option[Int] = 
    jdbcTemplate.queryForList(sql, classOf[java.lang.Long], toJavaObjectSeq(args:_*):_*).headOption.map(_.toInt)
  
  def update(sql:String, args:Any*):Int = 
	jdbcTemplate.update(sql, toJavaObjectSeq(args:_*):_*)
}

class NamedParameterJdbcTemplate(dataSource:DataSource) {
  val jdbcTemplate = new org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate(dataSource)

	def toJavaObjectMap(paramMap:Map[String,Any]):Map[String,Object] = paramMap.map { x=>
	  (x._1, 
	    if (x._2 == None || x._2 == null) {
	      null
	    } else if (x._2.isInstanceOf[Some[Any]]){
	    	x._2.asInstanceOf[Some[Any]].get.asInstanceOf[Object]
	    } else {
	    	x._2.asInstanceOf[Object]
	    }
	  )
	}

  def queryForSeq(sql:String, paramMap:Map[String,Any]):Seq[Row] =
  	jdbcTemplate.queryForList(sql, paramMap).map { x=> new Row(x) }
}

trait DataSourceSupport {
	@Autowired private var dataSource:DataSource = _

	def jdbcTemplate() = new JdbcTemplate(dataSource)
	def jdbcTemplate[T](f:(JdbcTemplate=>T)):T = {
		f.apply(new JdbcTemplate(dataSource))
	}

	def namedParameterJdbcTemplate() = new NamedParameterJdbcTemplate(dataSource)
	def namedParameterJdbcTemplate[T](f:(NamedParameterJdbcTemplate=>T)):T = {
		f.apply(new NamedParameterJdbcTemplate(dataSource))
	}
}
