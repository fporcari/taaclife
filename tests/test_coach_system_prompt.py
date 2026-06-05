"""Il system prompt deve contenere le clausole del contratto §8.

Se qualcuno annacqua il prompt (per esempio togliendo il divieto di
calcolare numeri o il tono non giudicante), questo test fallisce.
"""
from core.coach import SYSTEM_PROMPT


def test_prompt_states_non_medico() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "non sei un medico" in text
    assert "sostituisc" in text  # "sostituisce/sostituisci"


def test_prompt_forbids_calculating_or_estimating_numbers() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "non calcolare" in text or "non calcolare " in text
    assert "non stimare" in text or "non dedurlo" in text
    # Deve istruire a riprendere dal contesto.
    assert "context" in text  # blocco <context>


def test_prompt_states_say_missing_when_data_missing() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "non ho questo dato" in text


def test_prompt_states_non_judgmental_tone() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "non giudicante" in text
    assert "buon" in text and "cattiv" in text  # "buoni/cattivi"
    assert "colpa" in text


def test_prompt_states_use_user_preferences_and_database() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "preferenze" in text
    assert "database" in text or "data base" in text


def test_prompt_states_no_diagnostic_language() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "diagnostic" in text or "prescrittiv" in text
