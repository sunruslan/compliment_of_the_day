from datetime import date
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnableLambda
from pydantic import BaseModel, Field

from news import FreshHeadlinesRetriever
from setup import get_logger, get_config

logger = get_logger(__name__)


class ComplimentModel(BaseModel):
    """The funniest compliment based on recent news."""

    compliment: str = Field(description="A funny compliment based on recent news.")


class ComplimentGenerator:
    def __init__(
        self,
        news_client: FreshHeadlinesRetriever,
        llm_model: str = None,
        llm_temperature: float = None,
    ):
        self.news_client = news_client
        # Use config defaults if not provided
        llm_model = llm_model or get_config("llm.model", "gpt-4o-mini")
        llm_temperature = llm_temperature or get_config("llm.temperature", 0.7)

        try:
            self.llm = ChatOpenAI(model=llm_model, temperature=llm_temperature)
        except Exception as e:
            logger.error(f"Error initializing ChatOpenAI: {e}")
            self.llm = None
        self._setup_chains()

    def _setup_chains(self):
        if self.llm is None:
            self.single_compliment_chain = None
            self.select_best_compliment_chain = None
            return
        try:
            self.single_compliment_chain = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        get_config(
                            "prompts.system_compliment",
                            "Generate a funny compliment based on recent news:",
                        ),
                    ),
                    (
                        "user",
                        get_config(
                            "prompts.user_compliment",
                            "title: {title}\ndescription: {description}",
                        ),
                    ),
                ]
            ) | self.llm.with_structured_output(ComplimentModel)

            # Get ignored topics from config
            ignored_topics = get_config("ignored_topics", [])
            ignored_topics_str = ", ".join(ignored_topics) if ignored_topics else "none"

            # Get system_select prompt and format it with ignored topics
            system_select_template = get_config(
                "prompts.system_select",
                "Select the best among the following compliments:",
            )
            system_select_prompt = system_select_template.format(
                ignored_topics=ignored_topics_str
            )

            self.select_best_compliment_chain = ChatPromptTemplate.from_messages(
                [
                    ("system", system_select_prompt),
                    ("user", get_config("prompts.user_select", "{compliments}")),
                ]
            ) | self.llm.with_structured_output(ComplimentModel)
        except Exception as e:
            logger.error(f"Error setting up chains: {e}")
            self.single_compliment_chain = None
            self.select_best_compliment_chain = None

    @staticmethod
    def _extract_title_desc(headline):
        try:
            return {
                "title": getattr(headline, "title", ""),
                "description": getattr(headline, "description", ""),
            }
        except Exception as e:
            logger.error(f"Error extracting title/description: {e}")
            return {"title": "", "description": ""}

    @staticmethod
    def _join_compliments(results):
        try:
            parts = []
            for i in range(len(results)):
                compliment_obj = results.get(f"compliment_{i}")
                compliment_text = getattr(compliment_obj, "compliment", None)
                if compliment_text is None and isinstance(compliment_obj, dict):
                    compliment_text = compliment_obj.get("compliment", "")
                if compliment_text is None:
                    compliment_text = ""
                parts.append(f"Compliment {i + 1}: {compliment_text}")
            return {"compliments": "\n".join(parts)}
        except Exception as e:
            logger.error(f"Error joining compliments: {e}")
            return {"compliments": ""}

    def _get_headlines(self, target_date: date) -> List:
        try:
            return self.news_client.get_headlines(target_date)
        except Exception as e:
            logger.error(f"Error getting headlines: {e}")
            return []

    def generate_compliment_for_date(self, target_date: date) -> str | None:
        try:
            headlines = self._get_headlines(target_date)
            if not headlines:
                logger.warning("No news headlines available to generate compliment.")
                return None

            if (
                self.single_compliment_chain is None
                or self.select_best_compliment_chain is None
            ):
                logger.error("LLM chains are not properly initialized.")
                return None

            compliment_chains = {
                f"compliment_{i}": (
                    RunnableLambda(lambda d, i=i: d.get(f"headline_{i}"))
                    | RunnableLambda(self._extract_title_desc)
                    | self.single_compliment_chain
                )
                for i in range(len(headlines))
            }

            parallel_chain = RunnableParallel(**compliment_chains)

            chain = (
                parallel_chain
                | RunnableLambda(self._join_compliments)
                | self.select_best_compliment_chain
            )

            input_dict = {
                f"headline_{i}": headline for i, headline in enumerate(headlines)
            }
            try:
                result = chain.invoke(input_dict)
            except Exception as e:
                logger.error(f"Error invoking LLM chain: {e}")
                return None

            compliment_text = None
            if hasattr(result, "compliment"):
                compliment_text = result.compliment
            elif isinstance(result, dict):
                compliment_text = result.get("compliment")
            if not compliment_text:
                logger.warning("No compliment generated by the LLM.")
                compliment_text = None
            return compliment_text
        except Exception as e:
            logger.error(f"Unexpected error in generate_compliment_for_date: {e}")
            return None
