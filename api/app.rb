#!/usr/bin/ruby
# -*- coding: utf-8 -*-
require "rubygems"
require "groonga"
require "json"
require "sinatra"
require "mysql2"

def connection()
  Mysql2::Client.new(:host=>"localhost", :username=>"nihongodeok", :database=>"search")
end

get "/get_article" do
  url = params[:url]

  article_info = { :canonical_url=>url }
  if article_is_there then
    article = {:id=>1, :article_date=>nil, :created_at=>nil, :subject_en=>nil, :body_en=>nil, :subject_ja=>nil, :body_ja=>nil, :scraped_by=>nil}
    article_info[:article] = article
  else
  end

  content_type :json, :charset => 'utf-8'
  [ true, article_info ].to_json  
end

post "/push_article" do
  return 400 unless request.content_type == "application/json"

  content_type :json, :charset => 'utf-8'
  [ true ].to_json
end
