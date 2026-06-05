"""
app/bot/states.py — FSM holatlari (aiogram 3.x StatesGroup).
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class GroupCreate(StatesGroup):
    waiting_name = State()


class StudentAdd(StatesGroup):
    waiting_names = State()


class TestCreate(StatesGroup):
    waiting_title = State()
    choosing_qcount = State()
    choosing_vcount = State()
    entering_key = State()
    confirm = State()


class KeyEntry(StatesGroup):
    waiting_answers = State()
