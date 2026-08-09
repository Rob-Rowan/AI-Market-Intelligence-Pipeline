"""Sequential multi-stage AI content generation chain using the Gemini API."""

from __future__ import annotations

import logging
import os

from google import genai

logger = logging.getLogger(__name__)


class SequentialAIChain:
    """A 5-stage sequential AI chain for constrained content generation.

    Each stage builds on the previous stage's output and records its
    result in ``chain_memory`` for downstream audit logging.
    """

    def __init__(self) -> None:
        """Configure the Gemini client and initialise chain memory.

        Raises:
            ValueError: If ``GEMINI_API_KEY`` is not set.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not found.")

        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-flash"
        self.chain_memory: dict[str, str] = {}

    def run_stage(
        self, stage_name: str, instruction: str, context: str
    ) -> str:
        """Run a single stage of the AI chain against the Gemini model.

        Args:
            stage_name: Key used to store the output in ``chain_memory``.
            instruction: The model instruction for this stage.
            context: Input text derived from the previous stage.

        Returns:
            The model output text, or an empty string on API failure.
        """
        prompt = f"{instruction}\n\n{context}"
        try:
            response = self.client.models.generate_content(
                model=self.model_id, contents=prompt
            )
            result_text = response.text
        except Exception:
            logger.exception(
                "Gemini API call failed for stage '%s'.", stage_name
            )
            return ""
        self.chain_memory[stage_name] = result_text
        return result_text

    def execute_full_chain(self, raw_text: str) -> dict[str, str]:
        """Execute the full 5-stage AI pipeline.

        Args:
            raw_text: The source text to process.

        Returns:
            Dictionary mapping each stage name to its output text. Keys
            include ``summary``, ``action_items``, ``outline``,
            ``draft``, and ``Stage 5: Final Polish``.
        """
        facts = self.run_stage(
            stage_name="summary",
            instruction=(
                "Extract only the hard facts and numbers from this text. "
                "Do not add filler."
            ),
            context=raw_text,
        )
        sentiment = self.run_stage(
            stage_name="action_items",
            instruction=(
                "Based on these facts, determine if the market sentiment "
                "is Bullish, Bearish, or Neutral. Explain why in one "
                "short sentence."
            ),
            context=facts,
        )
        tldr = self.run_stage(
            stage_name="outline",
            instruction=(
                "Write exactly ONE sentence (maximum 15 words) "
                "summarising the core event. Be ruthless and concise."
            ),
            context=f"Facts: {facts}\nSentiment: {sentiment}",
        )
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