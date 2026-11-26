---
title: Google DeepMind releases Mass Spec Skills for Google Antigravity to identify
  molecules
slug: 2026-11-25-google-deepmind-releases-mass-spec-skills-for-google-antigravity-to-id
date: '2026-11-25T21:45:31Z'
summary: Google DeepMind has launched Mass Spec Skills, a set of tools for Google
  Antigravity that helps scientists interpret tandem mass spectra and propose molecular
  structures. The company says a lightweight model can match frontier-level retrieval
  accuracy when the skills are used.
tags:
- Google
- New models
- AI for business
why_it_matters: For organisations running mass spectrometry or chemical analysis,
  this shows AI agents being paired with established chemistry tools to speed up compound
  identification, though outputs are still intended for expert review.
sources:
- name: Google DeepMind
  url: https://deepmind.google/blog/interpreting-mass-spectra-with-google-antigravity/
  title: 'From spectrum to structure: Identifying molecules with Mass Spec Skills
    for Google Antigravity'
ai_drafted: true
---

Google DeepMind has shared Mass Spec Skills for Google Antigravity, a suite of skills that lets scientists use Gemini to interpret tandem mass spectra and set out the chemical evidence for review.

The company said the skills were built with analytical chemists and use community-developed tools. They run established mass spectrometry software and query public chemical databases on the user's behalf, then combine the results and reason about the chemistry.

Mass spectrometry measures the masses of charged molecules and the fragments they break into, but does not directly reveal structure. DeepMind said spectral library searches typically annotate only about 5% of measured spectra, and about 10% for human samples.

In a worked example, the agent reportedly narrowed a negative-mode spectrum to one molecular formula, then scored 845 isomers from PubChem against the observed fragments. It ruled out several close candidates by testing whether their bonds could plausibly produce the measured fragments, and identified a single structure.

DeepMind said the agent can take a prompt in plain language, without users configuring each underlying tool, and can also run individual steps such as peak annotation or comparing candidate isomers.

In a test of 100 compounds, DeepMind said accuracy stayed below 4% across three models when the agent had no internet access or skills. The source excerpt was cut off before the full results for the skills-enabled runs.

The company said the lightweight Gemini 3.8 Flash can match frontier-level retrieval accuracy with the skills enabled. The figures for that comparison were not included in the source text provided.
