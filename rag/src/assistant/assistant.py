"""Onboard medical assistant: crew data + most relevant protocol + protocols of the possible causes
+ retrieved chunks → MedGemma 1.5, which can ask for a whole document. The sources at the end of the answer are added
by the code from the documents the answer used.

From Python: answer("question", astronaut_id="A1")
From the terminal: python -m assistant.assistant "question" --astronaut A1 [--search-only]
"""

import argparse
import re

from assistant import crew, knowledge

MEDGEMMA_MODEL = "google/medgemma-1.5-4b-it"
MAX_NEW_TOKENS = 2048
REASONING_END = "<unused95>"  # MedGemma 1.5 may write "<unused94>thought ... <unused95>" before the answer
REASONING_START = "<unused94>"
MAX_DOCUMENT_READS = 2  # how many times the model can ask for READ_DOCUMENT
WORDS_PER_SEQUENCE = 5  # 5-word sequences to recognize which document the answer text comes from
MIN_SEQUENCES = 6  # at least 6 shared sequences (about one copied sentence) to count the document as a source
# For rephrased sentences, source = the document most similar to the answer sentences plus those within 0.02 of it
# (tuned on earlier answers: expected document among the sources 41/46; the 5 missing were wrong answers)
SIMILARITY_MARGIN = 0.02
MIN_SIMILARITY = 0.7
MIN_SENTENCE_WORDS = 6
MAX_CAUSES = 3  # how many possible causes to ask the model for before the answer
CAUSE_TOKENS = 80  # enough for 3 short lines: the extra call costs a few seconds

SYSTEM_PROMPT = """You are the onboard medical assistant for astronauts on a space station or exploration mission.
You support the crew and the Crew Medical Officer; you do not replace the flight surgeon.

Rules:
1. Base your answer on the CREW DATA and the KNOWLEDGE EXCERPTS you are given. If they are not enough, say so.
   Never invent values, drug doses or procedures.
2. Physiology in microgravity differs from Earth. Interpret vital signs against in-flight expected values and the
   crew member's own pre-flight baseline, never against terrestrial norms alone. Consider the cabin atmosphere
   (for example ppCO2) when it is relevant. In the crew data, compare the latest value and the last 7 days with the
   in-flight plateau: a recent move away from the plateau is what matters, even when the long-term change is expected.
3. If the CREW DATA lists ALERTS, deal with each alert first: say what it may mean using the excerpts and tell the
   crew to contact the flight surgeon. An alert is never normal adaptation to microgravity: the in-flight plateau
   already includes that adaptation, so an alert is a new change on top of it. If ALERTS is none, say clearly that
   the data are within the crew member's own in-flight range and do not raise an alarm; mention the next routine
   check instead.
4. For an emergency, give the protocol steps first, short and numbered, then tell the crew to contact the flight
   surgeon / Mission Control immediately. If a FULL PROTOCOL DOCUMENT is given and it matches the situation, follow
   its immediate actions in order. Never mix steps from different protocols (for example fire steps in a
   depressurization).
5. When the symptoms could have more than one cause, do not choose a single cause: list the possible causes (the
   most dangerous first) with the signs that tell them apart, and give the immediate actions for each dangerous cause
   that cannot be ruled out yet. Use the FULL PROTOCOL DOCUMENT and the POSSIBLE CAUSES excerpts for this.
6. Say where every piece of information comes from:
   - after each statement from the documents, the document id in square brackets, for example [sans-vision-changes];
   - for a drug, a dose or a limit, also the original source named in that document and its year;
   - for crew data, the parameter and mission day, for example (crew data: heart_rate, day 150).
   Do not write a list of sources at the end: it is added automatically from the ids you cite.
7. If you need another whole document to answer safely, reply with one single line:
   READ_DOCUMENT: <document id>
   and you will receive it. You can do this at most twice.
8. Be concise and practical: the reader is an astronaut, possibly during an emergency."""

# A short first call, before the answer: the model suggests the causes and the code looks up the protocol of each.
# This way a question like "elbow and tingling fingers during EVA" also brings decompression sickness,
# which a search on the words of the question alone did not find
CAUSES_PROMPT = """You are a space medicine expert supporting astronauts on a space station or exploration mission.
Read the QUESTION. If it describes symptoms, an injury or a medical emergency, list the possible causes the crew must
consider, the most dangerous first: at most 3, one per line, a few words each (for example: decompression sickness).
Do not answer the question and do not explain.
If the QUESTION does not describe a medical problem (for example it asks about a limit, a schedule or general
advice), reply only: NONE"""

# Loaded only once, on the first call
INDEX = None
MODEL = None
PROCESSOR = None


def shared_index() -> knowledge.Index:
    global INDEX
    if INDEX is None:
        INDEX = knowledge.Index()
    return INDEX


def generate(messages: list[dict], max_new_tokens: int = MAX_NEW_TOKENS) -> str:
    """The only place that talks to the model. For another backend (HTTP server, Ollama...) change only this.
    messages: [{"role": "system"|"user"|"assistant", "content": "text"}]."""
    global MODEL, PROCESSOR
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    if MODEL is None:
        MODEL = AutoModelForImageTextToText.from_pretrained(
            MEDGEMMA_MODEL, torch_dtype=torch.bfloat16, device_map="auto")
        PROCESSOR = AutoProcessor.from_pretrained(MEDGEMMA_MODEL)

    # The MedGemma processor wants the content as a list of parts
    model_messages = []
    for message in messages:
        parts = [{"type": "text", "text": message["content"]}]
        model_messages.append({"role": message["role"], "content": parts})

    inputs = PROCESSOR.apply_chat_template(
        model_messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt")
    inputs = inputs.to(MODEL.device)
    input_length = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        # Stops if the model starts its own list of sources (that is where it used to loop)
        # The token that opens the internal reasoning is banned (sometimes it did not close within the token limit)
        reasoning_token = PROCESSOR.tokenizer.convert_tokens_to_ids(REASONING_START)
        output = MODEL.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                                stop_strings=["Sources:"], tokenizer=PROCESSOR.tokenizer,
                                bad_words_ids=[[reasoning_token]])
    new_tokens = output[0][input_length:]
    text = PROCESSOR.decode(new_tokens, skip_special_tokens=True)
    return remove_repeated_lines(cut_source_list(strip_reasoning(text)))


def strip_reasoning(text: str) -> str:
    """Keeps only the answer, without the internal reasoning MedGemma 1.5 writes before it."""
    if REASONING_END in text:
        position = text.index(REASONING_END) + len(REASONING_END)
        text = text[position:]
    return text.strip()


def cut_source_list(text: str) -> str:
    """Removes any list of sources written by the model: the code adds it."""
    kept_lines = []
    for line in text.split("\n"):
        start = line.strip().strip("*#").strip().lower()
        if start.startswith("sources") or start.startswith("references"):
            break
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def remove_repeated_lines(text: str) -> str:
    """Removes lines identical to one already written: with greedy decoding the 4B model sometimes repeats the
    list of sources up to the token limit."""
    kept_lines = []
    seen = set()
    for line in text.split("\n"):
        clean = line.strip()
        if clean != "" and clean in seen:
            continue
        seen.add(clean)
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def causes_from_reply(reply: str) -> list[str]:
    """The causes, one per line, without numbers, dashes and bold; none if the model replies NONE."""
    causes = []
    for line in reply.split("\n"):
        clean = line.strip().lstrip("-*•0123456789.) ").strip("* ")
        if clean == "" or clean.endswith(":"):
            continue
        if clean.upper().startswith("NONE"):
            break
        causes.append(clean)
        if len(causes) == MAX_CAUSES:
            break
    return causes


def possible_causes(question: str) -> list[str]:
    """The possible causes the model sees in the question (empty list if it does not describe a medical problem)."""
    messages = [
        {"role": "system", "content": CAUSES_PROMPT},
        {"role": "user", "content": "QUESTION: " + question},
    ]
    return causes_from_reply(generate(messages, CAUSE_TOKENS))


def excerpts_text(chunks: list[dict]) -> str:
    """The retrieved chunks, each with its document id and its context line."""
    blocks = []
    for chunk in chunks:
        # Sources numbered like the [n] references inside the document text
        numbered_sources = []
        for number in range(len(chunk["sources"])):
            numbered_sources.append("[" + str(number + 1) + "] " + chunk["sources"][number])
        header = "--- document id: " + chunk["document_id"] + " | sources: " + " ".join(numbered_sources) + " ---"
        blocks.append(header + "\n" + chunk["text_with_context"])
    return "\n\n".join(blocks)


def user_message(question: str, crew_text: str, protocol_text: str, causes_text: str, chunks: list[dict]) -> str:
    text = "CREW DATA (long-term summary from onboard monitoring):\n" + crew_text
    if protocol_text != "":
        text = (text + "\n\nFULL PROTOCOL DOCUMENT (retrieved automatically: follow it only if it matches the situation"
                + " in the QUESTION):\n" + protocol_text)
    if causes_text != "":
        text = (text + "\n\nPOSSIBLE CAUSES (key sections of the protocols for other causes suggested for this"
                + " QUESTION: compare them, not all of them may apply):\n" + causes_text)
    text = (text + "\n\nKNOWLEDGE EXCERPTS (each starts with [document title › section] and the document summary):\n"
            + excerpts_text(chunks) + "\n\nQUESTION: " + question)
    return text


def search_query(question: str, crew_text: str, astronaut_id: str | None) -> str:
    """With an astronaut, the search also uses their data: the parameters in ALERT (e.g. 'heart rate') or, if there
    are none, the in-flight reference values. So 'how am I?' finds the right documents even without medical words."""
    if astronaut_id is None:
        return question
    alert_parameters = []
    for line in crew_text.split("\n"):
        if line.startswith("! "):
            alert_parameters.append(line[2:].split(" ")[0].replace("_", " "))
    if len(alert_parameters) == 0:
        return question + " (my in-flight vital signs compared with my pre-flight baseline)"
    return question + " (abnormal " + ", ".join(alert_parameters) + " compared with my in-flight baseline)"


def prepare_context(question: str, astronaut_id: str | None, causes: list[str] | None = None) -> dict:
    """Everything the model sees on the first turn: the candidate protocol in full (in tests the 4B model never asked
    for READ_DOCUMENT and mixed protocols), and the key sections of a different protocol for each possible cause.
    The chunks of these documents are removed from the excerpts so they are not repeated."""
    index = shared_index()
    if astronaut_id is None:
        crew_text = "Not provided for this question."
    else:
        crew_text = crew.long_term_summary(astronaut_id)

    found = index.search(search_query(question, crew_text, astronaut_id))
    found_chunks = found["chunks"]
    document_ids = found["documents"]
    protocol_id = found["protocol"]
    protocol_text = ""
    if protocol_id is not None:
        protocol_text = index.whole_document(protocol_id)

    cause_protocol_ids = []
    cause_texts = []
    if causes is not None:
        for cause in causes:
            cause_protocol_id = index.protocol_for_cause(cause)
            if cause_protocol_id is None or cause_protocol_id == protocol_id or cause_protocol_id in cause_protocol_ids:
                continue
            cause_protocol_ids.append(cause_protocol_id)
            cause_texts.append("Possible cause: " + cause + "\n" + index.key_sections(cause_protocol_id))

    chunks = []
    for chunk in found_chunks:
        if chunk["document_id"] != protocol_id and chunk["document_id"] not in cause_protocol_ids:
            chunks.append(chunk)
    return {
        "message": user_message(question, crew_text, protocol_text, "\n\n".join(cause_texts), chunks),
        "chunks": chunks,
        "protocol_id": protocol_id,
        "cause_protocol_ids": cause_protocol_ids,
        "document_ids": document_ids,
    }


def word_sequences(text: str) -> set:
    text_words = re.findall(r"[a-z0-9]+", text.lower())
    sequences = set()
    for start in range(len(text_words) - WORDS_PER_SEQUENCE + 1):
        sequences.add(" ".join(text_words[start:start + WORDS_PER_SEQUENCE]))
    return sequences


def documents_used_in_text(answer_text: str, consulted_documents: list[str]) -> list[str]:
    """The consulted documents the answer takes sentences from (shared word sequences) or rephrases (semantic
    similarity). The 4B model copies protocols but almost never writes [id]: this keeps sources explicit."""
    index = shared_index()
    answer_sequences = word_sequences(answer_text)
    used = []
    for document_id in consulted_documents:
        document_sequences = word_sequences(index.document(document_id)["body"])
        if len(answer_sequences & document_sequences) >= MIN_SEQUENCES:
            used.append(document_id)

    # Rephrased sentences: similarity between the answer sentences and the chunks of the consulted documents
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", answer_text):
        if len(sentence.split()) >= MIN_SENTENCE_WORDS:
            sentences.append(sentence.strip())
    similarities = index.document_similarity(sentences, consulted_documents)
    if len(similarities) > 0:
        highest = max(similarities.values())
        for document_id in consulted_documents:
            similarity = similarities.get(document_id, 0.0)
            close = similarity >= highest - SIMILARITY_MARGIN
            if close and similarity >= MIN_SIMILARITY and document_id not in used:
                used.append(document_id)
    return used


def sources_section(answer_text: str, consulted_documents: list[str]) -> tuple[str, list[str]]:
    """The list of sources is written by the code, with the real URLs: first the documents cited as [id], then those
    the answer takes its text from. If there are neither, it lists the consulted documents and says so."""
    index = shared_index()
    cited = []
    for document_id in re.findall(r"\[([a-z0-9-]+)\]", answer_text):
        if index.document(document_id) is not None and document_id not in cited:
            cited.append(document_id)
    for document_id in documents_used_in_text(answer_text, consulted_documents):
        if document_id not in cited:
            cited.append(document_id)
    lines = []
    if len(cited) > 0:
        lines.append("Sources:")
        listed = cited
    else:
        lines.append("Sources (documents consulted; none cited explicitly):")
        listed = consulted_documents
    for document_id in listed:
        document = index.document(document_id)
        lines.append("- [" + document_id + "] " + document["title"] + ": " + ", ".join(document["sources"]))
    return "\n".join(lines), cited


def requested_document(reply: str) -> str | None:
    """The id after READ_DOCUMENT, if the model asked for it (tolerates ` and * around the id)."""
    found = re.search(r"READ_DOCUMENT:\s*[`*\"']*([A-Za-z0-9_-]+)", reply)
    if found is None:
        return None
    return found.group(1).lower()


def remove_requests(reply: str) -> str:
    """Removes the READ_DOCUMENT lines left when the reading limit is reached."""
    kept_lines = []
    for line in reply.split("\n"):
        if "READ_DOCUMENT:" not in line:
            kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def answer(question: str, astronaut_id: str | None = None) -> dict:
    """Answers a crew question. Returns:
    {"answer": text with the sources at the end, "chunks": chunks in the excerpts, "protocol_id": protocol given in full,
     "causes": possible causes suggested by the model, "cause_protocol_ids": their protocols,
     "documents_read": ids asked with READ_DOCUMENT, "documents_cited": cited ids, "messages": conversation}."""
    index = shared_index()
    causes = possible_causes(question)
    context = prepare_context(question, astronaut_id, causes)
    chunks = context["chunks"]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context["message"]},
    ]
    documents_read = []
    reply = generate(messages)
    requested_id = requested_document(reply)
    while requested_id is not None and len(documents_read) < MAX_DOCUMENT_READS:
        documents_read.append(requested_id)
        document_text = index.whole_document(requested_id)
        if document_text is None:
            document_text = "There is no document with id '" + requested_id + "'. Use only ids shown in the excerpts."
        if len(documents_read) < MAX_DOCUMENT_READS:
            instruction = "Now answer the QUESTION (or request one more document if really needed)."
        else:
            instruction = "No more documents can be read. Now answer the QUESTION."
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": "FULL DOCUMENT:\n" + document_text
                         + "\n\nQUESTION: " + question + "\n" + instruction})
        reply = generate(messages)
        requested_id = requested_document(reply)

    if requested_id is not None:
        reply = remove_requests(reply)
    messages.append({"role": "assistant", "content": reply})

    consulted_documents = []
    if context["protocol_id"] is not None:
        consulted_documents.append(context["protocol_id"])
    for cause_protocol_id in context["cause_protocol_ids"]:
        consulted_documents.append(cause_protocol_id)
    for chunk in chunks:
        if chunk["document_id"] not in consulted_documents:
            consulted_documents.append(chunk["document_id"])
    sources_text, cited = sources_section(reply, consulted_documents)
    return {"answer": reply + "\n\n" + sources_text, "chunks": chunks, "protocol_id": context["protocol_id"],
            "causes": causes, "cause_protocol_ids": context["cause_protocol_ids"], "documents_read": documents_read,
            "documents_cited": cited, "messages": messages}


def main():
    parser = argparse.ArgumentParser(description="Onboard medical assistant (MedGemma 1.5 + RAG)")
    parser.add_argument("question")
    parser.add_argument("--astronaut", default=None, help="astronaut id, e.g. A1")
    parser.add_argument("--search-only", action="store_true",
                        help="only print the message that would go to the model (runs on CPU, no MedGemma)")
    arguments = parser.parse_args()

    if arguments.search_only:
        print(prepare_context(arguments.question, arguments.astronaut)["message"])
        return

    result = answer(arguments.question, arguments.astronaut)
    print(result["answer"])
    print("\nProtocol given in full:", result["protocol_id"])
    print("Possible causes:", result["causes"], "-> protocols:", result["cause_protocol_ids"])
    print("Documents read in full on request:", result["documents_read"])
    chunk_sources = []
    for chunk in result["chunks"]:
        chunk_sources.append(chunk["document_id"] + " › " + chunk["section"])
    print("Chunks used:", chunk_sources)


if __name__ == "__main__":
    main()
