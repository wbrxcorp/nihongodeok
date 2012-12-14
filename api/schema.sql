CREATE TABLE `articles` (
  `id` char(40) CHARACTER SET latin1 NOT NULL DEFAULT '',
  `url` varchar(255) NOT NULL,
  `site_id` varchar(64) DEFAULT NULL,
  `article_date` date DEFAULT NULL,
  `subject_en` text,
  `body_en` text,
  `subject_ja` text,
  `body_ja` text,
  `created_at` datetime NOT NULL,
  `scraped_by` varchar(64) CHARACTER SET latin1 DEFAULT NULL,
  `quality_issues` text,
  PRIMARY KEY (`id`),
  KEY `site_id` (`site_id`) USING BTREE,
  KEY `created_at` (`created_at`) USING BTREE,
  KEY `scraped_by` (`scraped_by`) USING BTREE,
  FULLTEXT KEY `articles_subject_en` (`subject_en`),
  FULLTEXT KEY `articles_body_en` (`body_en`),
  FULLTEXT KEY `articles_subject_ja` (`subject_ja`),
  FULLTEXT KEY `articles_body_ja` (`body_ja`)
) ENGINE=mroonga DEFAULT CHARSET=utf8;

CREATE TABLE `canonical_urls` (
  `url_id` char(40) CHARACTER SET latin1 NOT NULL DEFAULT '',
  `canonical_url` text,
  PRIMARY KEY (`url_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `contents_cache` (
  `id` char(40) CHARACTER SET latin1 NOT NULL DEFAULT '',
  `content_type` varchar(64) CHARACTER SET latin1 DEFAULT NULL,
  `contents` blob,
  `created_at` datetime DEFAULT NULL,
  `real_url` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `synonyms` (
  `id` varchar(255) NOT NULL,
  `words` varchar(1024) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=mroonga DEFAULT CHARSET=utf8;
