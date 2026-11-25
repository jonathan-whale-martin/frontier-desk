---
title: iFood scales coding agents across 15,000 repositories via internal REST API
slug: 2026-11-25-ifood-scales-coding-agents-across-15-000-repositories-via-internal-res
date: '2026-11-25T21:45:31Z'
summary: Brazilian food delivery company iFood describes its internal Remote Agents
  Platform, which runs agentic coding tasks across its code repositories, according
  to an OpenAI customer story.
tags:
- OpenAI
- AI for business
- New models
why_it_matters: Businesses building internal AI agents may find the account useful
  for thinking about run cost, structured output checks and asynchronous execution,
  though it describes one company's experience.
sources:
- name: OpenAI
  url: https://openai.com/business/customer-stories/ifood
  title: How iFood scales coding agents across 15,000 repositories
ai_drafted: true
problems:
- 'Unsupported claim: iFood is a Brazilian food delivery company. (Sources never describe
  iFood''s business or state it is Brazilian or a food delivery company.)'
- 'Unsupported claim: The figures have not been independently verified. (This is an
  added caveat by the draft writer; the sources do not discuss independent verification,
  though it is a reasonable editorial note rather than a sourced fact.)'
---

iFood, which maintains more than 15,000 code repositories, has built an internal Remote Agents Platform that turns engineering tasks into API calls, according to a customer story published on OpenAI's website.

Users submit a prompt and environment requirements through a REST call. The platform runs the task in an isolated remote sandbox and returns the result later as a merge request. Progress can be monitored in real time.

The workflow mixes deterministic steps, such as cloning the repository and publishing the merge request, with agentic execution. All runs use GPT-5.6 Luna. iFood said it chose the model for its balance of intelligence, efficiency and speed.

According to the story, the platform has completed more than 25,000 runs at an average inference cost of US$0.04 per run. iFood uses OpenAI's Structured Outputs to check that each session returns a response in a predefined format.

The platform powers an internal security product that scans repositories for vulnerable dependencies and attempts fixes. iFood's Victor Coelho said the accuracy of those fixes more than doubled after the migration. The story also says the number of vulnerabilities fixed more than doubled.

The platform was modelled on OpenAI's Batch and Agents APIs, the story says, but is internal to iFood. The figures come from iFood's account as published by OpenAI and have not been independently verified.
