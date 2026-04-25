# Qontext — Turn fragmented company data into a context base AI can operate on

**Track Prize:** 1g real gold bar (1x per member) + private dinner with Qontext
**Sponsor:** https://qontext.ai/?utm_source=luma

## Challenge

Most AI systems still reconstruct company reality at runtime: they pull scattered facts from mail, CRM, policies, tickets, docs, and chat, then hope the prompt is good enough. That does not scale.

In this track, you do not start with an agent. You start with company data. Qontext provides a simulated enterprise dataset including email, CRM, HR, policy documents, collaboration/workspace data, IT service data, and business records. The job is to turn that raw company state into a real, inspectable context base AI can work with and collaborate on top of.

Starts with unstructured and semi-structured internal company data. Ends with a virtual file system plus graph that makes this company legible to both machines and humans.

## Goal

Build a system that turns the dataset into a structured company memory:

- A **virtual file system** that documents the business:
  - static data (employees, customers, products)
  - procedural knowledge (processes, SOPs, rules)
  - trajectory information (tasks, projects, progress)
- **Explicit references** both inside and outside the graph: links to other files, and links to the underlying source records.
- **Interface(s)** that enable:
  - AI systems to efficiently retrieve context
  - business users and AI systems to inspect, validate, edit, and extend the company memory

## Criteria for a strong solution

- Generalize beyond the provided dataset and data format
- Resolve easy information conflicts automatically; involve humans where ambiguity actually matters
- Preserve provenance at the fact level and update automatically when source facts change

## Anti-patterns (what this is NOT)

- Dumping markdown into folders
- Building a documentation chatbot

It IS about designing a context base that is explainable, editable, robust under change, and useful in practice. Involve humans when it matters, take over their work where it does not.

## Other product thoughts

- Cover both graph construction and retrieval
- Treat the virtual file system as a product surface, not just storage
- Optimize for long-term maintainability by humans and machines
