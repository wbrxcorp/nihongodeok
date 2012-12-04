package com.walbrix.spring;

import org.springframework.context.ApplicationContextInitializer;
import org.springframework.web.context.ConfigurableWebApplicationContext;

class ContextProfileInitializer extends AnyRef
	with ApplicationContextInitializer[ConfigurableWebApplicationContext] {

	def initialize(ctx:ConfigurableWebApplicationContext) {
		var profiles = "prod";
		if (ctx.getServletContext().getServerInfo().startsWith("jetty")) {
			profiles = "dev";
		}
		ctx.getEnvironment().setActiveProfiles(profiles);
	}
}
