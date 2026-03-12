import spacy

nlp = spacy.load("en_core_web_sm")

def match_resume_to_job(resume, job_description):
    resume_doc = nlp(resume)
    job_doc = nlp(job_description)
    similarity = resume_doc.similarity(job_doc)
    feedback = "Strong match!" if similarity > 0.75 else "Resume could be improved with more relevant keywords."
    return round(similarity * 100, 2), feedback
