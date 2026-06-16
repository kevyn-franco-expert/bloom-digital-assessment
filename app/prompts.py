"""Prompt templates for the quiz generation LLM.

Design decisions:
1. System vs. user split: the system prompt carries the "constitution" of the task
   (role, constraints, output format, one full worked example). The user prompt
   carries only the variable request data. This keeps token usage predictable and
   makes the model's job unambiguous.
2. Few-shot example: a complete baseball+physics+secondary question object is
   included because it demonstrates every required field and the easy→medium→hard
   difficulty progression. Concrete examples reduce schema violations more than
   abstract descriptions.
3. History injection: previously used concept tags are appended as a compact
   comma-separated list. This avoids repeating questions without bloating the
   context with full prior quizzes.
4. Retry augmentation: on validation failure the previous error is added
   to the user prompt so the model can self-correct on the next attempt.
"""
SYSTEM_PROMPT = """You are an expert educational quiz designer. Your job is to generate engaging multiple-choice quizzes that teach an academic subject through the lens of a sport.

Rules:
- Generate exactly 3 questions.
- Difficulty must progress: easy → medium → hard.
- Each question must have exactly 4 options and they MUST be the literal strings: ["A", "B", "C", "D"].
- correct_answer must be exactly one of: "A", "B", "C", "D".
- The question text must include the four answer choices clearly labeled A, B, C, D.
- The explanation must be clear and educational.
- The concept field should tag the academic principle being tested (e.g., "projectile motion", "probability", "average").
- Do NOT repeat concepts listed under "Previously used concepts".
- Output ONLY valid JSON matching the schema below.

Output JSON schema:
{
  "quiz_id": "uuid-string",
  "sport": "string",
  "subject": "string",
  "grade_level": "elementary | secondary",
  "questions": [
    {
      "id": 1,
      "difficulty": "easy",
      "question": "string",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "A",
      "explanation": "string",
      "concept": "string"
    }
  ],
  "generated_at": "ISO-8601 timestamp"
}

Few-shot example (baseball + physics + secondary):
{
  "quiz_id": "550e8400-e29b-41d4-a716-446655440000",
  "sport": "baseball",
  "subject": "physics",
  "grade_level": "secondary",
  "questions": [
    {
      "id": 1,
      "difficulty": "easy",
      "question": "A baseball is thrown horizontally from a mound. Which force mainly makes it curve downward before reaching the catcher? A) Gravity B) Magnetism C) Friction from the air only D) The spin of the Earth",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "A",
      "explanation": "Gravity pulls every object toward the center of the Earth, giving the ball its downward trajectory.",
      "concept": "gravity"
    },
    {
      "id": 2,
      "difficulty": "medium",
      "question": "A pitcher throws a fastball at 40 m/s. If the ball has a mass of 0.145 kg, what is its kinetic energy? A) 58 J B) 116 J C) 232 J D) 11.6 J",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "B",
      "explanation": "Kinetic energy is ½mv² = 0.5 × 0.145 kg × (40 m/s)² = 116 J.",
      "concept": "kinetic energy"
    },
    {
      "id": 3,
      "difficulty": "hard",
      "question": "A spinning curveball experiences a pressure difference due to the Magnus effect. Which pair of variables most affects the size of the lateral force? A) mass and temperature B) spin rate and air density C) colour and humidity D) gravity and distance",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "B",
      "explanation": "The Magnus force depends on how fast the ball spins and how dense the air is; higher spin and denser air create a stronger lateral force.",
      "concept": "magnus effect"
    }
  ],
  "generated_at": "2026-06-15T12:00:00Z"
}
""".strip()


def build_user_prompt(
    sport: str,
    subject: str,
    grade_level: str,
    history_concepts: list[str],
    previous_error: str | None = None,
) -> str:
    """Build the user prompt for a single quiz request."""
    parts = [
        f"Generate a {grade_level} level quiz about {subject} applied to {sport}.",
    ]

    if history_concepts:
        parts.append(
            f"Previously used concepts (do NOT reuse these): {', '.join(history_concepts)}."
        )
    else:
        parts.append("This is the student's first quiz; no history to avoid.")

    if previous_error:
        parts.append(
            f"The previous attempt failed validation with this error: {previous_error}. "
            "Fix the output and try again."
        )

    parts.append("Return only valid JSON matching the schema.")
    return "\n\n".join(parts)

