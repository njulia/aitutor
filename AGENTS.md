1. The ai tutor will be used by 1 million primary school students who has very short attention spans and low patience for loading wheels. 
2. Improve the design to reduce performance, reduce latency, reduce token usage. Don't use langchain if it caused latency and performance issues.
3. Don't always call LLM, use memory, Database or RAG. 
4. Use REVIEW_HOMEWORK_PROMPT to generate homework follows the DfE Programme of Study. The questions match the perfenece of primary school student.
5. Use REVIEW_HOMEWORK_PROMPT and REVIEW_UPLOADED_HOMEWORK_PROMPT to generate simple answers and basic explanations.
6. Use EXPLAIN_DEEP_PROMPT to generate explain in detail, at least including step-by-step explanation, weakness analysis and “Why did I get this wrong?".
7. Use IMPROVE_PRACTICE_PROMPT to give more practice which can help the student progress, like similar questions and adaptive follow-up tutoring.