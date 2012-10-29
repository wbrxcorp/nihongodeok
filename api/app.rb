#!/usr/bin/ruby
# -*- coding: utf-8 -*-
require "rubygems"
require "groonga"
require "json"
require "sinatra"
require "mysql2"

before do
  @conn = Mysql2::Client.new(:host=>"localhost", :username=>"nihongodeok", :database=>"search")
end

after do
  @conn.close
end

get "/get_article" do
  url = params[:url]

  article_info = { :canonical_url=>url }
  
  row = @conn.query("select * from articles where id=sha1('#{@conn.escape(url)}')").first
  p url
  if row != nil then
    article = {:id=>row["id"], :date=>row["article_date"], :created_at=>row["created_at"], :subject_en=>row["subject_en"], :body_en=>row["body_en"], :subject_ja=>row["subject_ja"], :body_ja=>row["body_ja"], :site_id=>row["site_id"], :scraped_by=>row["scraped_by"]}
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

  p @conn.query("insert into articles(id,url,article_date,subject_#{language},body_#{language},site_id,scraped_by,created_at) values(sha1('#{@conn.escape(url)}'), '#{@conn.escape(url)}','#{date}','#{@conn.escape(subject)}', '#{@conn.escape(body)}','#{@conn.escape(site_id)}','#{@conn.escape(scraped_by)}',now())")

  content_type :json, :charset => 'utf-8'
  [ true ].to_json
end
