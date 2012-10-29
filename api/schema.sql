create table canonical_urls(
  url_id char(40) charset latin1,
  url text,
  primary key(url_id)
);

create table articles (
  id serial primary key,
  url varchar(255) unique not null,
  site_id varchar(64) charset latin1,
  article_date date,
  subject_en text,
  body_en text,
  subject_ja text,
  body_ja text,
  created_at datetime not null,
  scraped_by varchar(64),
  quality_issues text,
  fulltext index(subject_en),
  fulltext index(body_en),
  fulltext index(subject_ja),
  fulltext index(body_ja),
  fulltext index(quality_issues),
  index using btree(site_id),
  index using btree(created_at),
  index using btree(scraped_by)
) engine=mroonga;
