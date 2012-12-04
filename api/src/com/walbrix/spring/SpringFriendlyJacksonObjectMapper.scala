package com.walbrix.spring

import java.util.List
import collection.JavaConversions.asScalaBuffer

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.Module

class SpringFriendlyJacksonObjectMapper extends ObjectMapper {
	def setModules(modules:List[Module])
	{
		for (module <- modules) {
			this.registerModule(module);
		}
	}
}
