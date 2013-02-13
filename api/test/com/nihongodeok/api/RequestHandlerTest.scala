package com.nihongodeok.api

import org.jsoup.Jsoup
import java.io.ByteArrayInputStream
import java.net.URL

object RequestHandlerTest {

  def main(args: Array[String]): Unit = {
    val doc = Jsoup.connect("http://www.livemint.com/Page/Id/2.0.778536885").get()
    println(doc.select("meta[property=og:url]"))
    println(new RequestHandler().getCanonicalURL(doc))
  }

}