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
import scala.runtime.RichInt
import org.springframework.dao.DataIntegrityViolationException

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
	
	implicit def row2article(row:Row):Article = {
		Article(
	        id=row("id"),
	        url=row("url"),
	        siteId=row("site_id"),
	        date=row.option("article_date"),
	        createdAt=row("created_at"),
	        scrapedBy=row("scraped_by"),
	        subjectEn=row("subject_en"),
	        bodyEn=row("body_en"),
	        subjectJa=row.option("subject_ja"),	  
	        bodyJa=row.option("body_ja"))	  
	}
	
	implicit def row2article(row:Option[Row]):Option[Article] = {
	  return row.map { x=> x }
	}

	def getArticle(articleId:String):Option[Article] = { 
	  (articleId.length() match {
		  case 16 =>
		    jdbcTemplate.queryForSeq("select * from articles where id like ?", articleId + '%')
		  case _ =>
		    jdbcTemplate.queryForSeq("select * from articles where id=?", articleId)
	  }).headOption
	}
	
	@RequestMapping(value=Array("get_article/{articleId}"), method = Array(RequestMethod.GET))
	@ResponseBody
	def getArticle(response:HttpServletResponse, @PathVariable articleId:String):Article = {
	  getArticle(articleId).getOrElse {
	    response.sendError(HttpServletResponse.SC_NOT_FOUND); null
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
	  jdbcTemplate.queryForSeq("select content_type,contents,real_url from contents_cache where id=sha1(?) and created_at >= date_sub(now(), interval ? second)", url, ttl).headOption.foreach {row=>
	    return (row("content_type"), decompressXZ(row("contents")), row("real_url"))
	  }
	  def removeUtmParams(url:String):String = {
		  val splitted = url.split("\\?",2)
		  if (splitted.length > 1) {
			  val filteredParams = splitted(1).split("&").filter(!_.startsWith("utm_"))
			  if (filteredParams.length > 0) { 
			    splitted(0) + '?' + (filteredParams mkString "&")
			  } else splitted(0)
		  } else {
			  return url 
		  }
	  }
	  val httpClient = new DefaultHttpClient()
	  val httpContext = new BasicHttpContext()
	  val httpGet = new HttpGet(url)
	  httpGet.setHeader("User-Agent", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
	  val response = httpClient.execute(httpGet, httpContext)
	  val currentReq = httpContext.getAttribute(ExecutionContext.HTTP_REQUEST).asInstanceOf[HttpUriRequest]
	  val currentHost = httpContext.getAttribute(ExecutionContext.HTTP_TARGET_HOST).asInstanceOf[HttpHost]
	  val realURL = removeUtmParams(if (currentReq.getURI().isAbsolute()) { currentReq.getURI().toString() } else { currentHost.toURI() + currentReq.getURI() })
	  val baos = new ByteArrayOutputStream()
	  val entity = response.getEntity()
	  val contentType = entity.getContentType().getValue()
	  entity.writeTo(baos)
	  val content = baos.toByteArray()
	  try {
		  jdbcTemplate.update("replace into contents_cache(id,real_url,content_type,contents,created_at) values(sha1(?), ?, ?, ?, now())", url, realURL, contentType, compressXZ(content))
	  }
	  catch {
	    case _ => 0;
	  }
	  (contentType, content, realURL)
	} 

	def getCanonicalURL(doc:org.jsoup.nodes.Document):Option[String] = {
	  doc.select("head > link[rel=canonical]").first() match {
	    case null => Option(doc.select("meta[property=og:url]").first()).map(_.attr("content"))
	    case x => Some(x.attr("href"))
	  }
	}

	@RequestMapping(value=Array("get_article"), method = Array(RequestMethod.GET))
	@ResponseBody
	def getArticleByURL(@RequestParam(value="url",required=true) url:String):(String, Option[Article]) = {
	  val jt = jdbcTemplate
	  jt.queryForSeq("select * from articles where id=sha1(?)", url).headOption.foreach { x=> return (url, Some(x))}

	  val canonicalURL = jt.queryForStringOption("select canonical_url from canonical_urls where url_id=sha1(?)", url).getOrElse {
	    val (contnetType, content, realURL) = _cacheableFetch(url)
	    val doc = Jsoup.parse(new ByteArrayInputStream(content), "UTF-8", realURL)
	    getCanonicalURL(doc) match {
	      case Some(canonicalURL) =>
	      	jt.update("replace into canonical_urls(url_id,canonical_url) values(sha1(?),?)", url, canonicalURL)
	      	canonicalURL
	      case None=>
	      	if (!url.equals(realURL)) {
	      		jt.update("replace into canonical_urls(url_id,canonical_url) values(sha1(?),?)", url, realURL)
	      	}
	      	realURL
	    }
	  }
	  
	  (canonicalURL, jt.queryForSeq("select * from articles where id=sha1(?)", canonicalURL).headOption)
	}

	@RequestMapping(value=Array("push_article"), method = Array(RequestMethod.POST))
	@ResponseBody
	def pushArticle(request:HttpServletRequest, response:HttpServletResponse):(Boolean,Option[String]) = {
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
	  val articleId = jdbcTemplate.queryForString("select sha1(?)", url)

	  (jdbcTemplate.update("insert into articles(id,url,article_date,subject_" + language + ",body_" + language + ",site_id,scraped_by,created_at)" +
	  		" values(?,?,?,?,?,?,?,now())", articleId, url, date, subject, body, siteId, scrapedBy) > 0, Some(articleId))
	}

	@RequestMapping(value=Array("list"), method = Array(RequestMethod.GET))
	@ResponseBody
	def list():Map[String,Seq[(String,Int)]] = {
		val scrapers = jdbcTemplate.queryForSeq("select scraped_by,count(scraped_by) cnt from articles group by scraped_by").map { row=>
			(row("scraped_by"), row("cnt"))
		}

		val sites = jdbcTemplate.queryForSeq("select site_id,count(site_id) cnt from articles group by site_id").map { row=>
			(row("site_id"), row("cnt"))
		}

		Map("scrapers"->scrapers, "sites"->sites)
	}

	@RequestMapping(value=Array("latest_articles"), method = Array(RequestMethod.GET))
	@ResponseBody
	def latestArticles(@RequestParam(value="site_id", defaultValue="") siteId:String,
	    @RequestParam(value="scraped_by", defaultValue="") scrapedBy:String,
	    @RequestParam(value="limit",defaultValue="100") limit:Int):Seq[Article] = {
	  val jt = jdbcTemplate
      ((siteId.nonEmpty,scrapedBy.nonEmpty) match {
        case (true, true) => 
          jt.queryForSeq("select * from articles where site_id=? and scraped_by=? order by created_at desc limit ?", 
              siteId, scrapedBy, limit)
        case (true, false) => 
          jt.queryForSeq("select * from articles where site_id=? order by created_at desc limit ?", 
              siteId, limit)
        case (false, true) => 
          jt.queryForSeq("select * from articles where scraped_by=? order by created_at desc limit ?", 
              scrapedBy, limit)
        case (false, false) => 
          jt.queryForSeq("select * from articles order by created_at desc limit ?", limit)
      }).map { row=> row2article(row) }
	}

	@RequestMapping(value=Array("/latest_articles/ja"), method = Array(RequestMethod.GET))
	@ResponseBody
	def latestArticlesJa(@RequestParam(value="site_id", defaultValue="") siteId:String,
	    @RequestParam(value="date", defaultValue="") date:String,
	    @RequestParam(value="page", defaultValue="1") page:Int):Seq[Article] = 
	  ((siteId.nonEmpty,date.nonEmpty,
	      "select * from articles where (subject_ja is not null and subject_ja != '') and (body_ja is not null and body_ja != '')") match {
	    case (true, true, baseSQL) =>
	      jdbcTemplate.queryForSeq(baseSQL + " and site_id=? and article_date=? order by created_at desc limit 20", siteId.toLowerCase(), date)
	    case (true, false, baseSQL) =>
	      jdbcTemplate.queryForSeq(baseSQL + " and site_id=? order by article_date desc,created_at desc limit 20", siteId.toLowerCase())
	    case (false, true, baseSQL) =>
	      jdbcTemplate.queryForSeq(baseSQL + " and article_date=? order by created_at desc limit 20", date)
	    case (false, false, baseSQL) =>
	      jdbcTemplate.queryForSeq(baseSQL + " order by article_date desc,created_at desc limit 20")
	  }).map { row=> row2article(row) }

	@RequestMapping(value=Array("/articles_to_be_translated"), method = Array(RequestMethod.GET))
	@ResponseBody
	def articlesToBeTranslated():Seq[Article] = 
	  jdbcTemplate.queryForSeq("select * from articles where (subject_ja = '' or body_ja = '') " +
	  		"and (match(subject_en) against('+Japan' in boolean mode) OR match(body_en) against('+Japan' in boolean mode)) " +
	  		"and site_id not in('The Japan Times','Japan Today') " + 
	  		"order by article_date desc,created_at desc limit 20").map(implicitly[Row=>Article])

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
	        urlencode("id,url,site_id,article_date,created_at,scraped_by,subject_en,body_en,subject_ja,body_ja," +
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
	        	scrapedBy=elem.get(5).asText(),
	        	subjectEn=elem.get(6).asText(), bodyEn=elem.get(7).asText(),
	        	subjectJa=Some(elem.get(8).asText()), bodyJa=Some(elem.get(9).asText())),
	        snippets=Map("subject_en"->elem.get(10),
	            "body_en"->elem.get(11),
	            "subject_ja"->elem.get(12),
	            "body_ja"->elem.get(13))
          )
	  })
	}

	@RequestMapping(value=Array("clear_query_cache"), method=Array(RequestMethod.POST))
	@ResponseBody
	def clearQueryCache(@RequestParam(value="table_name", required=true) tableName:String):Tuple1[Boolean] = {
	    val url = "http://%s:%d/d/load?table=%s&values=%s".format(groongaHost, groongaPort, tableName, "[]")
	    Tuple1(new ObjectMapper().readTree(new URL(url)).get(0).get(0).asInt() == 0)
	}

	@RequestMapping(value=Array("synonyms"), method=Array(RequestMethod.GET))
	@ResponseBody
	def synonyms(@RequestParam(value="q", defaultValue="") q:String):Map[String,String] = {
	  (q.isEmpty match {
	    case true => jdbcTemplate.queryForSeq("select id,words from synonyms order by id")
	    case false => jdbcTemplate.queryForSeq("select id,words from synonyms where id like ? order by id", "%" + q + "%")
	  }).map { row=> (row("id"), row("words"))}.toMap
	}

	@RequestMapping(value=Array("synonym"), method=Array(RequestMethod.POST))
	@ResponseBody
	def updateSynonym(@RequestParam(value="keyword",required=true) keyword:String,
	    @RequestParam(value="synonyms", required=true) synonyms:String):(Boolean, Option[AnyRef]) = {
	  (jdbcTemplate.update("replace into synonyms(id,words) values(?,?)", keyword, synonyms) > 0, None)
	}

	@RequestMapping(value=Array("bag_of_words/{article_id}"), method=Array(RequestMethod.POST))
	@ResponseBody
	def bagOfWords(response:HttpServletResponse, @PathVariable(value="article_id") articleId:String,
	    @RequestParam(value="words_en") wordsEn:String,
	    @RequestParam(value="words_ja") wordsJa:String):(Boolean, Option[AnyRef]) = {
    	jdbcTemplate.queryForSeq("select * from articles where id=?", articleId).headOption match {
    	  case Some(row) => 
    	    //val createdAt = row.get("created_at").asInstanceOf[java.sql.Timestamp]
    	    //val date = row.get("article_date").asInstanceOf[java.sql.Date]
    	    val rst = jdbcTemplate.update("replace into bag_of_words(article_id,words_en,words_ja) values(?,?,?)", articleId, wordsEn, wordsJa)
    	    (rst > 0, None)
    	  case None => 
    	    response.sendError(HttpServletResponse.SC_NOT_FOUND);
    	    (false, None)
    	}
	}

    case class RelatedArticle(
	    id:String, 
	    url:String,
	    @JsonProperty(value="site_id") siteId:String,
	    date:Option[String],
	    @JsonProperty(value="subject_en") subjectEn:Option[String] = None,
	    @JsonProperty(value="body_en") bodyEn:Option[String] = None,
	    @JsonProperty(value="subject_ja") subjectJa:Option[String] = None,
	    @JsonProperty(value="body_ja") bodyJa:Option[String] = None)

	@RequestMapping(value=Array("related_articles/{article_id}"), method=Array(RequestMethod.GET))
	@ResponseBody
	def relatedArticles(response:HttpServletResponse, @PathVariable(value="article_id") articleId:String,
	    @RequestParam(value="limit", defaultValue="5") limit:Int,
	    @RequestParam(value="language",required=false) language:String):Seq[RelatedArticle] = {
	  getArticle(articleId) match {
	    case Some(article) =>
	      jdbcTemplate.queryForSeq("select words_en from bag_of_words where article_id like ?", articleId + '%').headOption match {
	        case Some(row) =>
		      jdbcTemplate.queryForSeq("select match(words_en) against(?) as score,id,url,site_id,article_date,subject_en,body_en,subject_ja,body_ja from bag_of_words,articles where article_id=id and id not like ? order by score desc limit ?", row("words_en"), articleId + '%', limit).map { row =>
		    	RelatedArticle(id=row("id"),
		            url=row("url"),
		            siteId=row("site_id"),
		            date=row.option("article_date"),
		            subjectEn=row.option("subject_en"),
		            bodyEn=row.option("body_en"),
		            subjectJa=row.option("subject_ja"),
		            bodyJa=row.option("body_ja"))
		      }
	        case None => Seq()
	      }
	    case None => response.sendError(HttpServletResponse.SC_NOT_FOUND); null
	  }
	}

    case class UserProfile ()
 
	@RequestMapping(value=Array("user/{external_id}"), method=Array(RequestMethod.POST))
	@ResponseBody
	def getUser(@PathVariable(value="external_id") externalId:String):(Int,UserProfile) = {
      jdbcTemplate.update("insert ignore into users(external_id,created_at) values(?,now())", externalId)
      val userId = jdbcTemplate.queryForInt("select id from users where external_id=?", externalId)
      jdbcTemplate.update("insert ignore into user_profiles(user_id, updated_at) values(?,now())", userId)
      (userId, UserProfile())
	}

    case class Interpretation (subject:Option[String] = None, summary:Option[String] = None,
        commentary:Option[String] = None,
        @JsonProperty(value="commentary_format") commentaryFormat:Option[String] = None, 
        public:Boolean = false,
        @JsonProperty(value="user_profile") userProfile:Option[UserProfile] = None)

    @RequestMapping(value=Array("article/{articleId}/interpretation"), method = Array(RequestMethod.GET))
	@ResponseBody
	def getInterpretations(response:HttpServletResponse, @PathVariable articleId:String):Seq[Interpretation] = {
      Seq(Interpretation(userProfile=Some(UserProfile())))
	}

    @RequestMapping(value=Array("article/{articleId}/interpretation/{userId}"), method = Array(RequestMethod.GET))
	@ResponseBody
	def getInterpretation(response:HttpServletResponse, @PathVariable articleId:String, @PathVariable userId:Int):Interpretation = {
      jdbcTemplate.queryForSeq("select * from interpretations where article_id=? and user_id=?", 
          articleId, userId).headOption match {
        case Some(row) => Interpretation(
            subject = row.option("subject"),
            summary = row.option("summary"),
            commentary = row.option("commentary"),
            commentaryFormat = row.option("commentary_format") )
        case None => response.sendError(HttpServletResponse.SC_NOT_FOUND); null
      }
	}

    @RequestMapping(value=Array("article/{_articleId}/interpretation/{userId}"), method = Array(RequestMethod.POST))
	@ResponseBody
	def postInterpretation(response:HttpServletResponse, @PathVariable _articleId:String, @PathVariable userId:Int,
	    @RequestParam(value="subject") subject:String,
	    @RequestParam(value="summary") summary:String,
	    @RequestParam(value="commentary") commentary:String,
	    @RequestParam(value="commentary_format") commentaryFormat:String,
	    @RequestParam(value="public") public:java.lang.Boolean):(Boolean, Boolean, Option[AnyRef]) = {
      val articleId = getArticle(_articleId) match {
        case Some(article) => article.id
        case None =>
        	response.sendError(HttpServletResponse.SC_NOT_FOUND)
        	return (false, false, None)
      }
      val jt = jdbcTemplate
      jt.update("insert ignore into interpretations(article_id,user_id,created_at,public) values(?,?,now(),false)", articleId, userId)
      if (subject != null) {
    	  jt.update("update interpretation set subject=? where article_id=? and user_id=?", subject, articleId, userId)
      }
      if (summary != null) {
    	  jt.update("update interpretation set summary=? where article_id=? and user_id=?", summary, articleId, userId)
      }
      if (commentary != null) {
    	  jt.update("update interpretation set commentary=? where article_id=? and user_id=?", commentary, articleId, userId)
      }
      if (commentaryFormat != null) {
    	  jt.update("update interpretation set commentary_format=? where article_id=? and user_id=?", commentaryFormat, articleId, userId)
      }
      val disclosed = public match {
        case null => false
        case _ =>
    	  jt.update("update interpretation set public=? where article_id=? and user_id=?", public, articleId, userId)
    	  jt.update("update interpretation set disclosed_at=now() where disclosed_at is null and public=true and article_id=? and user_id=?", articleId, userId) > 0
      }
      jt.update("update interpretation set updated_at=now() where article_id=? and user_id=?", articleId, userId)
      (true, disclosed, None)
	}

    @RequestMapping(value=Array("suggest_site_id"), method = Array(RequestMethod.GET))
	@ResponseBody
	def suggestSiteId(@RequestParam(value="url",required=true) url:String):Tuple1[Option[String]] = {
		jdbcTemplate.queryForSeq("select regex,site_id from url_to_site_ids").foreach { row =>
		  if (new scala.util.matching.Regex(row("regex")).findFirstIn(url) != None) {
			  return Tuple1(Some(row("site_id")))
		  }
		}
		return Tuple1(None)
    }
}
