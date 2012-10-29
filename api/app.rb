#!/usr/bin/ruby
# -*- coding: utf-8 -*-
require "rubygems"
require "groonga"
require "json"
require "sinatra"
require "mysql2"
require "nokogiri"
require "open-uri"

before do
  @conn = Mysql2::Client.new(:host=>"localhost", :username=>"nihongodeok", :database=>"search")
end

after do
  @conn.close
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
      doc = Nokogiri.HTML(open(url))
      canonical = doc.search("/html/head/link[@rel='canonical']").first
      if canonical && canonical.key?("href") then
        canonical_url = canonical[:href]
        @conn.query("replace into canonical_urls(url_id,canonical_url) values(sha1('#{@conn.escape(url)}'),'#{@conn.escape(canonical_url)}')")
      end
    end
    if url != canonical_url then
      article_row = @conn.query("select * from articles where id=sha1('#{@conn.escape(url)}')").first
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
