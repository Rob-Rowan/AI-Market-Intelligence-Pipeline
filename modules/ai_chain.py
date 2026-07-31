"""Sequential multi-stage AI content generation chain using the Gemini API."""

import os

from google import genai


class SequentialAIChain:
    """A 5-stage sequential AI chain for constrained content generation.

    Executes a strict pipeline of prompts against the Gemini model to
    produce concise, scannable executive briefs from raw text. Each
    stage builds on the output of the previous one, and all intermediate
    results are stored in ``chain_memory`` for audit-logging.

    Attributes:
        chain_memory: Dictionary mapping stage names to their output
            text.
    """

    def __init__(self) -> None:
        """Initialise the chain and configure the Gemini API client.

        Reads the ``GEMINI_API_KEY`` environment variable and creates a
        :class:`genai.Client` instance.

        Raises:
            ValueError: If ``GEMINI_API_KEY`` is not set.
        """
        try:
            self.api_key = os.environ.get("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "GEMINI_API_KEY environment variable not found."
                )

            self.client = genai.Client(api_key=self.api_key)
            self.model_id = "gemini-2.5-flash"
            self.chain_memory: dict[str, str] = {}
        except Exception as e:
            print(f"Error during initialisation: {e}")
            raise

    def run_stage(
        self, stage_name: str, instruction: str, context: str
    ) -> str:
        """Run a single stage of the AI chain.

        Sends a prompt (constructed from *instruction* and *context*) to
        the Gemini model and stores the result in ``chain_memory`` under
        *stage_name*.

        Args:
            stage_name: Unique key for this stage (used in
                ``chain_memory`` and audit logging).
            instruction: The system-style instruction telling the model
                what to produce.
            context: The input text to process.

        Returns:
            The model's response text, or an empty string on failure.
        """
        prompt = f"{instruction}\n\n{context}"
        try:
            response = self.client.models.generate_content(
                model=self.model_id, contents=prompt
            )
            result_text = response.text
            self.chain_memory[stage_name] = result_text
            return result_text
        except Exception as e:
            print(
                f"An API error occurred during stage '{stage_name}': {e}"
            )
            return ""

    def execute_full_chain(self, raw_text: str) -> dict[str, str]:
        """Execute the full 5-stage AI pipeline.

        Produces a summary, sentiment analysis, TL;DR, impact bullets,
        and a final polished brief from the provided *raw_text*.

        Args:
            raw_text: The source text to process (e.g. an RSS article
                or transcript).

        Returns:
            Dictionary mapping each stage name to its output text.
            Keys include ``"summary"``, ``"action_items"``,
            ``"outline"``, ``"draft"``, and
            ``"Stage 5: Final Polish"``.
        """
        # Stage 1: Extract Facts
        facts = self.run_stage(
            stage_name="summary",
            instruction=(
                "Extract only the hard facts and numbers from this text. "
                "Do not add filler."
            ),
            context=raw_text,
        )

        # Stage 2: Sentiment Analysis
        sentiment = self.run_stage(
            stage_name="action_items",
            instruction=(
                "Based on these facts, determine if the market sentiment "
                "is Bullish, Bearish, or Neutral. Explain why in one "
                "short sentence."
            ),
            context=facts,
        )

        # Stage 3: The TL;DR
        tldr = self.run_stage(
            stage_name="outline",
            instruction=(
                "Write exactly ONE sentence (maximum 15 words) "
                "summarising the core event. Be ruthless and concise."
            ),
            context=f"Facts: {facts}\nSentiment: {sentiment}",
        )

        # Stage 4: Impact Bullet Points
        draft = self.run_stage(
            stage_name="draft",
            instruction=(
                "Write exactly 3 extremely short bullet points "
                "(maximum 10 words per bullet) outlining the market "
                "impact. Do not use introductory phrases, just give "
                "the data."
            ),
            context=tldr,
        )

        # Stage 5: Final Polish
        self.run_stage(
            stage_name="Stage 5: Final Polish",
            instruction=(
                "Format the following data exactly as shown below, "
                "using Markdown. Do NOT add an introduction, conclusion, "
                "or any placeholders.\n\n"
                "**Executive TL;DR:** [Insert Stage 3 TL;DR]\n"
                "**Market Sentiment:** [Insert Stage 2 Sentiment]\n\n"
                "**Key Market Impacts:**\n"
                "[Insert Stage 4 Bullets]"
            ),
            context=(
                f"Stage 2: {sentiment}\n"
                f"Stage 3: {tldr}\n"
                f"Stage 4: {draft}"
            ),
        )

        return self.chain_memory