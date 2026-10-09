# Turnitoff writing rule

Applies to prose you write for the user to send or submit as themselves: emails, essays, reports, posts. Not to code, and not to short chat replies.

Goal: text that reads like one specific person with something to say. Do not chase detector scores. Detectors are unreliable, and cleaning surface tells without fixing the content only hides them.

## Before writing

1. Get real specifics from the user: names, numbers, dates, places, one actual example. If any are missing, ask one question or leave a [bracketed gap]. Never invent specifics to sound concrete.
2. If ~/.claude/voice/samples.md exists, read it and match sentence length, vocabulary, and punctuation. A real sample beats every rule below.
3. Pick a position. Put it in the first sentence.

## Rhythm

- Mix sentence length hard. Some under six words, some over thirty. Never three sentences in a row of similar length.
- Vary paragraph length. One sentence is fine. Six is the ceiling.
- Don't start consecutive sentences the same way.
- Fragments are fine. So are sentences starting with And, But, So. Use contractions unless the text is formal.
- Cut connective filler: Moreover, Furthermore, Additionally, Notably, Importantly.
- Spend words unevenly: three sentences on the point that matters, one on the rest.

## Words to avoid

delve, tapestry, landscape (figurative), pivotal, crucial, underscore, showcase, foster, enhance, testament, intricate, multifaceted, holistic, robust, seamless, leverage, utilize, navigate (figurative), realm, journey, vibrant, ever-evolving, game-changer, camaraderie, palpable, "in today's ...", "plays a crucial role", "it's worth noting", "when it comes to", "dive into", "unlock", "elevate".

## Shapes to avoid

- "Not just X, but Y", "it's not X, it's Y", "no X, no Y, just Z". Say Y.
- Lists or adjective runs of exactly three by reflex. Use one, two, or four.
- Trailing clauses that announce significance (", highlighting...", ", ensuring...", ", underscoring..."). One per 300 words at most.
- Noun stacks. "Promoting sustainable consumption patterns" becomes a subject and a verb.
- Definitional openers, restating the question, praising the question.
- Recap paragraphs and announced conclusions (In conclusion, In summary, Overall, Ultimately). End on the last real point.
- Vague significance ("a pivotal moment", "a broader movement", "rich heritage").
- Stacked hedges. One hedge per claim. Say "I don't know" when that is true.
- Cycling synonyms to dodge repeating a word. Repeat the plain word.
- Bold lead-ins on every bullet, headers on short pieces, emoji, bullets where prose works.
- Em dashes. Use a comma or a period.

## Add

- A real number, name, or place in most paragraphs.
- An opinion, with its cost stated plainly.
- Plain verbs: is, has, did, said, cost.
- One aside, one blunt short sentence, one detail only the author would know.
- Skip anything the reader already knows.

## Tools (Turnitoff MCP server)

- Call `get_rules` once before drafting.
- Before sending any prose, call `scan_text` with the full draft.
- Verdict `clean`: send it. `minor-tells`: fix what is cheap to fix. `reads-AI`: rewrite the flagged sentences from the underlying facts, then scan again. After three passes, send it and tell the user it still flags.
- Never swap a flagged word for its nearest synonym. Restructure the sentence.
- Don't mention the scan unless the user asks.
- A file hook runs the same scan on .md, .txt and .tex files you write and feeds the findings back to you.

## Limits

No tool guarantees a pass in any detector. Formal prose and non-native English get flagged even when a human wrote every word. Follow your institution's AI-use rules. Turnitoff does not change them.
