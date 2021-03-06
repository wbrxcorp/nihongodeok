#!/usr/bin/ruby
# -*- coding: utf-8 -*-
require "rubygems"
require "groonga"
require "json"
require "sinatra"
require "mysql2"
require "nokogiri"
require "open-uri"
require "xz"

before do
  @conn = Mysql2::Client.new(:host=>"localhost", :username=>"nihongodeok", :database=>"search")
end

after do
  @conn.close
end

get "/get_article/:article_id" do
  article_id = params[:article_id]
  row = @conn.query("select * from articles where id='#{@conn.escape(article_id)}'").first
  return 404 if row == nil

  content_type :json, :charset => 'utf-8'

  {:id=>row["id"], :url=>row["url"], :date=>row["article_date"], :created_at=>row["created_at"], :subject_en=>row["subject_en"], :body_en=>row["body_en"], :subject_ja=>row["subject_ja"], :body_ja=>row["body_ja"], :site_id=>row["site_id"], :scraped_by=>row["scraped_by"]}.to_json
end

get "/get_article" do
  url = params[:url]

  article_row = @conn.query("select * from articles where id=sha1('#{@conn.escape(url)}')").first
  if article_row == nil then
    canonical_url_row = @conn.query("select canonical_url from canonical_urls where url_id=sha1('#{@conn.escape(url)}')").first
    canonical_url = nil
    if canonical_url_row != nil then
      canonical_url = canonical_url_row["canonical_url"]
    else
      _content_type, contents = cacheable_fetch(url)
      doc = Nokogiri.HTML(contents)
      canonical = doc.search("/html/head/link[@rel='canonical']").first
      if canonical && canonical.key?("href") then
        canonical_url = canonical[:href]
        @conn.query("replace into canonical_urls(url_id,canonical_url) values(sha1('#{@conn.escape(url)}'),'#{@conn.escape(canonical_url)}')")
      end
    end
    if canonical_url != nil && url != canonical_url then
      article_row = @conn.query("select * from articles where id=sha1('#{@conn.escape(canonical_url)}')").first
      url = canonical_url
    end
  end

  article_info = { :canonical_url=>url }
  
  if article_row != nil then
    article = {:id=>article_row["id"], :date=>article_row["article_date"], :created_at=>article_row["created_at"], :subject_en=>article_row["subject_en"], :body_en=>article_row["body_en"], :subject_ja=>article_row["subject_ja"], :body_ja=>article_row["body_ja"], :site_id=>article_row["site_id"], :scraped_by=>article_row["scraped_by"]}
    article_info[:article] = article
  end

  content_type :json, :charset => 'utf-8'
  [ true, article_info ].to_json  
end

post "/push_article" do
  return 400 unless request.content_type == "application/json"

  r = JSON.parse(request.body.read)
  url = r["url"]
  language = r["language"]
  subject = r["subject"]
  body = r["body"]
  scraped_by = r["scraped_by"]
  site_id = r["site_id"]
  date = r["date"]

  @conn.query("insert into articles(id,url,article_date,subject_#{language},body_#{language},site_id,scraped_by,created_at) values(sha1('#{@conn.escape(url)}'), '#{@conn.escape(url)}','#{date}','#{@conn.escape(subject)}', '#{@conn.escape(body)}','#{@conn.escape(site_id)}','#{@conn.escape(scraped_by)}',now())")

  content_type :json, :charset => 'utf-8'
  [ true ].to_json
end

get "/list" do
  scrapers = @conn.query("select scraped_by,count(scraped_by) cnt from articles group by scraped_by").collect {|row|
    [ row["scraped_by"], row["cnt"] ]
  }
  sites = @conn.query("select site_id,count(site_id) cnt from articles group by site_id").collect {|row|
    [ row["site_id"], row["cnt"] ]
  }

  content_type :json, :charset => 'utf-8'
  { :scrapers=>scrapers, :sites=>sites }.to_json
end

get "/latest_articles" do
  scraped_by = params[:scraped_by]
  site_id = params[:site_id]
  limit = params[:limit]
  if limit == nil then
    limit = 100
  else
    limit = limit.to_i
  end
  
  conditions = []
  conditions << "scraped_by='#{@conn.escape(scraped_by)}'" if scraped_by != nil && scraped_by != ""
  conditions << "site_id='#{@conn.escape(site_id)}'" if site_id != nil && site_id != ""
  if conditions.size > 0 then
    conditions = "where " + conditions.join(' and ') 
  else
    conditions = ""
  end

  articles = @conn.query("select * from articles #{conditions} order by created_at desc limit #{limit}").collect {|row|
    {:id=>row["id"], :url=>row["url"], :date=>row["article_date"], :created_at=>row["created_at"], :subject_en=>row["subject_en"], :body_en=>row["body_en"], :subject_ja=>row["subject_ja"], :body_ja=>row["body_ja"], :site_id=>row["site_id"], :scraped_by=>row["scraped_by"]}
  }

  content_type :json, :charset => 'utf-8'
  articles.to_json
end

post "/delete_article" do
  article_id = params[:article_id]
  return 400 if article_id == nil

  @conn.query("delete from articles where id='#{@conn.escape(article_id)}'")

  content_type :json, :charset => 'utf-8'
  [true].to_json
end

get "/statistics" do
  conditions = [ [ "today", "created_at>=current_date()"],
                 [ "yday", "created_at>=date_sub(current_date(),INTERVAL 1 DAY) and created_at < current_date()" ],
                 [ "-2days", "created_at>=date_sub(current_date(),INTERVAL 2 DAY) and created_at < date_sub(current_date(),INTERVAL 1 DAY)" ],
                 [ "-3days", "created_at>=date_sub(current_date(),INTERVAL 3 DAY) and created_at < date_sub(current_date(),INTERVAL 2 DAY)" ],
                 [ "-4days", "created_at>=date_sub(current_date(),INTERVAL 4 DAY) and created_at < date_sub(current_date(),INTERVAL 3 DAY)" ],
                 [ "-5days", "created_at>=date_sub(current_date(),INTERVAL 5 DAY) and created_at < date_sub(current_date(),INTERVAL 4 DAY)" ],
                 [ "-6days", "created_at>=date_sub(current_date(),INTERVAL 6 DAY) and created_at < date_sub(current_date(),INTERVAL 5 DAY)" ]]
  daily = []
  conditions.each {|condition|
    cnt = @conn.query("select count(*) cnt from articles where #{condition[1]}").first["cnt"]
    daily << [ condition[0], cnt ]
  }

  content_type :json, :charset => 'utf-8'
  {:daily=>daily}.to_json
end

def cacheable_fetch(url, ttl=3600)
  row = @conn.query("select content_type,contents from contents_cache where id=sha1('#{@conn.escape(url)}') and created_at >= date_sub(now(), interval #{ttl} second)").first
  if row != nil then
    #p "cache hit"
    contents = XZ.decompress(row["contents"])
    content_type = row["content_type"]
  else
    content_type, contents = open(url) {|f|
      [f.content_type, f.read]
    }
    @conn.query("replace into contents_cache(id,content_type,contents,created_at) values(sha1('#{@conn.escape(url)}'), '#{@conn.escape(content_type)}', '#{@conn.escape(XZ.compress(contents))}', now())")
  end
  return [content_type, contents]
end

get "/cacheable_fetch" do
  url = params[:url]
  return 400 if url == nil

  begin
    _content_type, contents = cacheable_fetch(url)
  rescue SocketError
    return 503
  rescue OpenURI::HTTPError=>e
    return e.io.status[0].to_i
  end
  content_type _content_type
  contents
end
