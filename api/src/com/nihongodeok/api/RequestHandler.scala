package com.nihongodeok.api

import java.util.Calendar
import java.io.{ByteArrayInputStream,ByteArrayOutputStream}
import java.net.{URL, URLEncoder}
import javax.servlet.http.{HttpServletRequest,HttpServletResponse}
import collection.JavaConversions.{asScalaBuffer,asScalaIterator}
import org.springframework.stereotype.Controller
import org.springframework.transaction.annotation.Transactional
import org.springframework.web.bind.annotation.{RequestMapping, PathVariable,RequestParam, RequestMethod, ResponseBody}
import org.jsoup.Jsoup
import org.apache.http.client.methods.HttpGet
import org.apache.http.impl.client.DefaultHttpClient
import org.tukaani.xz.{XZInputStream,SingleXZInputStream,XZOutputStream,X86Options,LZMA2Options}
import com.fasterxml.jackson.annotation.JsonProperty
import com.fasterxml.jackson.databind.{ObjectMapper,JsonNode}
import org.apache.http.HttpHost
import org.apache.http.client.methods.HttpUriRequest
import org.apache.http.protocol.{BasicHttpContext,ExecutionContext}

@Controller
@RequestMapping(Array(""))
@Transactional
class RequestHandler extends AnyRef with DataSourceSupport {

	val groongaHost = "localhost"
	val groongaPort = 10041

	case class Article(
	    id:String, 
	    url:String,
	    @JsonProperty(value="site_id") siteId:String,
	    date:Option[String],
	    @JsonProperty(value="created_at") createdAt:java.sql.Timestamp,
	    @JsonProperty(value="scraped_by") scrapedBy:String,
	    @JsonProperty(value="subject_en") subjectEn:String,
	    @JsonProperty(value="body_en") bodyEn:String,
	    @JsonProperty(value="subject_ja") subjectJa:Option[String] = None,
	    @JsonProperty(value="body_ja") bodyJa:Option[String] = None,
	    @JsonProperty(value="canonical_url") canonicalURL:Option[String] = None)
	
	case class SearchResult(
	    article:Article,
	    snippets:Map[String,Seq[String]]
	)

	implicit def date2string(date:java.sql.Date):String = {
	  val cal = java.util.Calendar.getInstance()
	  cal.setTime(date)
	  "%04d-%02d-%02d".format(cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH))
	}
	
	implicit def row2article(row:java.util.Map[String,Object]):Article = {
		Article(
	        id=row.get("id").asInstanceOf[String],
	        url=row.get("url").asInstanceOf[String],
	        siteId=row.get("site_id").asInstanceOf[String],
	        date=Option(row.get("article_date").asInstanceOf[java.sql.Date]),
	        createdAt=row.get("created_at").asInstanceOf[java.sql.Timestamp],
	        scrapedBy=row.get("scraped_by").asInstanceOf[String],
	        subjectEn=row.get("subject_en").asInstanceOf[String],
	        bodyEn=row.get("body_en").asInstanceOf[String],
	        subjectJa=Option(row.get("subject_ja").asInstanceOf[String]),	  
	        bodyJa=Option(row.get("body_ja").asInstanceOf[String]))	  
	}

	@RequestMapping(value=Array("get_article/{articleId}"), method = Array(RequestMethod.GET))
	@ResponseBody
	def getArticle(response:HttpServletResponse, @PathVariable articleId:String):Article = {
	  jdbcTemplate.queryForList("select * from articles where id=?", articleId).headOption match {
	    case Some(row) => row
	    case None => response.sendError(HttpServletResponse.SC_NOT_FOUND); null
	  }
	}
	
	def decompressXZ(src:Array[Byte]):Array[Byte] = {
	  val is = new XZInputStream(new ByteArrayInputStream(src))
	  val buf = new Array[Byte](1024)
	  val baos = new ByteArrayOutputStream()
	  var i = is.read(buf)
	  while (i > 0) {
	   baos.write(buf, 0, i)
	   i = is.read(buf)
	  }
	  return baos.toByteArray
	}
	
	def compressXZ(src:Array[Byte]):Array[Byte] = {
	  val baos = new ByteArrayOutputStream()
	  val os = new XZOutputStream(baos, Array(new X86Options(),new LZMA2Options()))
	  os.write(src)
	  os.flush()
	  os.close()
	  return baos.toByteArray
	}
	
	def _cacheableFetch(url:String, ttl:Int = 3600):(String,Array[Byte], String) = {
	  jdbcTemplate.queryForList("select content_type,contents,real_url from contents_cache where id=sha1(?) and created_at >= date_sub(now(), interval ? second)", url, ttl.asInstanceOf[Integer]).headOption.foreach {row=>
	    return (row.get("content_type").asInstanceOf[String], decompressXZ(row.get("contents").asInstanceOf[Array[Byte]]), row.get("real_url").asInstanceOf[String])
	  }
	  val httpClient = new DefaultHttpClient()
	  val httpContext = new BasicHttpContext()
	  val httpGet = new HttpGet(url)
	  val response = httpClient.execute(httpGet, httpContext)
	  val currentReq = httpContext.getAttribute(ExecutionContext.HTTP_REQUEST).asInstanceOf[HttpUriRequest]
	  val currentHost = httpContext.getAttribute(ExecutionContext.HTTP_TARGET_HOST).asInstanceOf[HttpHost]
	  val realURL = if (currentReq.getURI().isAbsolute()) { currentReq.getURI().toString() } else { currentHost.toURI() + currentReq.getURI() }
	  val baos = new ByteArrayOutputStream()
	  val entity = response.getEntity()
	  val contentType = entity.getContentType().getValue()
	  entity.writeTo(baos)
	  val content = baos.toByteArray()
	  jdbcTemplate.update("replace into contents_cache(id,real_url,content_type,contents,created_at) values(sha1(?), ?, ?, ?, now())", url, realURL, contentType, compressXZ(content))
	  (contentType, content, realURL)
	} 
	
	@RequestMapping(value=Array("get_article"), method = Array(RequestMethod.GET))
	@ResponseBody
	def getArticleByURL(@RequestParam(value="url",required=true) url:String):(String, Option[Article]) = {
	  val jt = jdbcTemplate
	  jt.queryForList("select * from articles where id=sha1(?)", url).headOption.foreach { x=> return (url, Some(x))}

	  val canonicalURL = jt.queryForList("select canonical_url from canonical_urls where url_id=sha1(?)", classOf[String], url).headOption.getOrElse {
	    val (contnetType, content, realURL) = _cacheableFetch(url)
	    val doc = Jsoup.parse(new ByteArrayInputStream(content), "UTF-8", realURL)
	    Option(doc.select("head > link[rel=canonical]").first()).map { x=>
	      val canonicalURL = x.attr("href")
	      jt.update("replace into canonical_urls(url_id,canonical_url) values(sha1(?),?)", url, canonicalURL)
	      canonicalURL
	    }.getOrElse {
	      if (!url.equals(realURL)) {
	    	jt.update("replace into canonical_urls(url_id,canonical_url) values(sha1(?),?)", url, realURL)
	      }
	      realURL
	    }
	  }
	  
	  (canonicalURL, jt.queryForList("select * from articles where id=sha1(?)", canonicalURL).headOption.map(row2article))
	}

	@RequestMapping(value=Array("push_article"), method = Array(RequestMethod.POST))
	@ResponseBody
	def pushArticle(request:HttpServletRequest, response:HttpServletResponse):(Boolean,Option[AnyRef]) = {
	  if (!request.getContentType().equals("application/json")) {
	    response.sendError(HttpServletResponse.SC_BAD_REQUEST)
	    return (false, None)
	  }
	  val mapper = new ObjectMapper()
	  val json = mapper.readTree(request.getInputStream())
	  val url = json.get("url").asText()
	  val language = json.get("language").asText()
	  val subject = json.get("subject").asText()
	  val body = json.get("body").asText()
	  val scrapedBy = json.get("scraped_by").asText()
	  val siteId = json.get("site_id").asText()
	  val date = json.get("date").asText()

	  (jdbcTemplate.update("insert into articles(id,url,article_date,subject_" + language + ",body_" + language + ",site_id,scraped_by,created_at)" +
	  		" values(sha1(?), ?,?,?,?,?,?,now())", url, url, date, subject, body, siteId, scrapedBy) > 0, None)
	}

	@RequestMapping(value=Array("list"), method = Array(RequestMethod.GET))
	@ResponseBody
	def list():Map[String,Seq[(String,Int)]] = {
		val scrapers = jdbcTemplate.queryForList("select scraped_by,count(scraped_by) cnt from articles group by scraped_by").map { row=>
			(row.get("scraped_by").asInstanceOf[String], row.get("cnt").asInstanceOf[Long].toInt)
		}.toSeq

		val sites = jdbcTemplate.queryForList("select site_id,count(site_id) cnt from articles group by site_id").map { row=>
			(row.get("site_id").asInstanceOf[String], row.get("cnt").asInstanceOf[Long].toInt)
		}.toSeq

		Map("scrapers"->scrapers, "sites"->sites)
	}

	@RequestMapping(value=Array("latest_articles"), method = Array(RequestMethod.GET))
	@ResponseBody
	def latestArticles(@RequestParam(value="site_id", defaultValue="") siteId:String,
	    @RequestParam(value="scraped_by", defaultValue="") scrapedBy:String,
	    @RequestParam(value="limit",defaultValue="100") limit:Int):Seq[Article] = {
	  val jt = jdbcTemplate
      asScalaBuffer((siteId.nonEmpty,scrapedBy.nonEmpty) match {
        case (true, true) => 
          jt.queryForList("select * from articles where site_id=? and scraped_by=? order by created_at desc limit ?", 
              siteId, scrapedBy, limit.asInstanceOf[Integer])
        case (true, false) => 
          jt.queryForList("select * from articles where site_id=? order by created_at desc limit ?", 
              siteId, limit.asInstanceOf[Integer])
        case (false, true) => 
          jt.queryForList("select * from articles where scraped_by=? order by created_at desc limit ?", 
              scrapedBy, limit.asInstanceOf[Integer])
        case (false, false) => 
          jt.queryForList("select * from articles order by created_at desc limit ?", limit.asInstanceOf[Integer])
      }).map { row=> row2article(row) }
	}

	@RequestMapping(value=Array("/latest_articles/ja"), method = Array(RequestMethod.GET))
	@ResponseBody
	def latestArticlesJa(@RequestParam(value="page", defaultValue="1") page:Int):Seq[Article] = 
	  jdbcTemplate.queryForList("select * from articles where (subject_ja is not null and subject_ja != '') and (body_ja is not null and body_ja != '') order by article_date desc,created_at desc limit 20").map { row=>
	  	row2article(row)
	  }

	@RequestMapping(value=Array("/articles_to_be_translated"), method = Array(RequestMethod.GET))
	@ResponseBody
	def articlesToBeTranslated():Seq[Article] = 
	  jdbcTemplate.queryForList("select * from articles where (subject_ja = '' or body_ja = '') " +
	  		"and (match(subject_en) against('+Japan' in boolean mode) OR match(body_en) against('+Japan' in boolean mode)) " +
	  		"and site_id != 'The Japan Times' " + 
	  		"order by article_date desc,created_at desc limit 20").map { row=>
	  	row2article(row)
	  }

	@RequestMapping(value=Array("/translate_article"), method = Array(RequestMethod.POST))
	@ResponseBody
	def translateArticle(
	    @RequestParam(value="article_id", required=true) articleId:String,
	    @RequestParam(value="language", required=true) language:String,
	    @RequestParam(value="subject", required=true) subject:String,
	    @RequestParam(value="body", required=true) body:String):(Boolean,Option[AnyRef]) = {
	  (jdbcTemplate.update("update articles set subject_" + language + "=?, body_" + language + "=? where id=?",
	      subject, body, articleId) > 0, None)
	}

	@RequestMapping(value=Array("delete_article"), method = Array(RequestMethod.POST))
	@ResponseBody
	def deleteArticle(response:HttpServletResponse, 
	    @RequestParam(value="article_id",required=true) articleId:String):(Boolean,Option[AnyRef]) =
	  (jdbcTemplate.update("delete from articles where id=?", articleId) > 0, None)

	@RequestMapping(value=Array("statistics"), method = Array(RequestMethod.GET))
	@ResponseBody
	def statistics():Map[String,Seq[(String,Int)]] = {
	  val conditions = Seq(
	      ("today", "created_at>=current_date()"),
	      ("yday", "created_at>=date_sub(current_date(),INTERVAL 1 DAY) and created_at < current_date()"),
	      ("-2days", "created_at>=date_sub(current_date(),INTERVAL 2 DAY) and created_at < date_sub(current_date(),INTERVAL 1 DAY)"),
	      ("-3days", "created_at>=date_sub(current_date(),INTERVAL 3 DAY) and created_at < date_sub(current_date(),INTERVAL 2 DAY)"),
	      ("-4days", "created_at>=date_sub(current_date(),INTERVAL 4 DAY) and created_at < date_sub(current_date(),INTERVAL 3 DAY)"),
	      ("-5days", "created_at>=date_sub(current_date(),INTERVAL 5 DAY) and created_at < date_sub(current_date(),INTERVAL 4 DAY)"),
	      ("-6days", "created_at>=date_sub(current_date(),INTERVAL 6 DAY) and created_at < date_sub(current_date(),INTERVAL 5 DAY)"))

	  val daily = conditions.map { day=>
	    (day._1, jdbcTemplate.queryForInt("select count(*) cnt from articles where "+ day._2))
	  }
	  Map("daily"->daily)
	}

	@RequestMapping(value=Array("cacheable_fetch"), method = Array(RequestMethod.GET))
	def cacheableFetch(response:HttpServletResponse, @RequestParam(value="url",required=true) url:String) = {
	  val (contentType, content, realURL) = _cacheableFetch(url)
	  response.setContentType(contentType)
	  response.getOutputStream().write(content)
	}
	
	@RequestMapping(value=Array("search"), method=Array(RequestMethod.GET))
	@ResponseBody
	def search(@RequestParam(value="q",required=true) q:String,
	    @RequestParam(value="offset", defaultValue="0") offset:Int,
	    @RequestParam(value="limit", defaultValue="10") limit:Int,
	    @RequestParam(value="order_by", defaultValue="-_score") orderBy:String):(Int, Seq[SearchResult]) = {
	  
	  def urlencode(value:String):String = { URLEncoder.encode(value, "UTF-8")}
	  val snippetExpr = "body_en" // "subject_en+body_en+subject_ja+body_ja"
	  val url = "http://%s:%d/d/select?table=%s&query=%s&query_expansion=synonyms.words&command_version=2&match_columns=%s&offset=%d&limit=%d&sortby=%s&output_columns=%s"
	    .format(groongaHost, groongaPort,"articles",urlencode(q),"subject_en||body_en||subject_ja||body_ja", offset, limit, orderBy, 
	        urlencode("id,url,site_id,article_date,created_at,scraped_by,subject_en,body_en," +
	        		"snippet_html(subject_en),snippet_html(body_en),snippet_html(subject_ja),snippet_html(body_ja)"))
	  //println(url)
	  val results = new ObjectMapper().readTree(new URL(url))
	  val count = results.get(1).get(0).get(0).get(0).asInt()
	  
	  implicit def double2datestr(value:Double):String = { new java.sql.Date((value * 1000).toLong) }
	  implicit def double2timestamp(value:Double):java.sql.Timestamp = { new java.sql.Timestamp((value * 1000).toLong) }
	  val iter = results.get(1).get(0).elements()
	  iter.next()
	  iter.next()
	  implicit def node2strseq(value:JsonNode):Seq[String] = value.iterator.toSeq.map {x=>x.asText()}
	  (count, iter.toSeq.map { elem=> 
	    SearchResult(
	        article=Article(id=elem.get(0).asText(),url=elem.get(1).asText(),siteId=elem.get(2).asText(),
	        	date=({x:JsonNode => if (x.isNull) { None } else { Some[String](x.asDouble()) }})(elem.get(3)),
	        	createdAt=elem.get(4).asDouble(),
	        	scrapedBy=elem.get(5).asText(),subjectEn=elem.get(6).asText(),
	        	bodyEn=elem.get(7).asText()),
	        snippets=Map("subject_en"->elem.get(8),
	            "body_en"->elem.get(9),
	            "subject_ja"->elem.get(10),
	            "body_ja"->elem.get(11))
          )
	  })
	}

	@RequestMapping(value=Array("clear_query_cache"), method=Array(RequestMethod.POST))
	@ResponseBody
	def clearQueryCache(@RequestParam(value="table_name", required=true) tableName:String):Tuple1[Boolean] = {
	    val url = "http://%s:%d/d/load?table=%s&values=%5B%5D".format(groongaHost, groongaPort, tableName)
	    Tuple1(new ObjectMapper().readTree(new URL(url)).get(0).get(0).asInt() == 0)
	}

	@RequestMapping(value=Array("synonyms"), method=Array(RequestMethod.GET))
	@ResponseBody
	def synonyms(@RequestParam(value="q", defaultValue="") q:String):Map[String,String] = {
	  asScalaBuffer(q.isEmpty match {
	    case true => jdbcTemplate.queryForList("select id,words from synonyms order by id")
	    case false => jdbcTemplate.queryForList("select id,words from synonyms where id like ? order by id", "%" + q + "%")
	  }).map { row=> (row.get("id").asInstanceOf[String], row.get("words").asInstanceOf[String])}.toMap
	}

	@RequestMapping(value=Array("synonym"), method=Array(RequestMethod.POST))
	@ResponseBody
	def updateSynonym(@RequestParam(value="keyword",required=true) keyword:String,
	    @RequestParam(value="synonyms", required=true) synonyms:String):(Boolean, Option[AnyRef]) = {
	  (jdbcTemplate.update("replace into synonyms(id,words) values(?,?)", keyword, synonyms) > 0, None)
	}

}
