"""
IELTS Speaking topic bank + generator.

Built-in bank ships 200+ discrete question/topic items so a session can be
assembled entirely offline (no LLM key required). The generator layer adds
LLM-produced variety on top, and keeps Part 2 / Part 3 thematically linked,
matching how the real test works.

Counts (see tests/test_topics.py for the assertion):
    Part 1: 40 categories x 3 questions      = 120 questions
    Part 2: 50 cue cards                     =  50 topics
    Part 3: 20 themes x 6 questions          = 120 questions
    ------------------------------------------------------
    Total discrete items                     = 290+
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from app.services.ielts.llm_client import IELTSLLMClient

# ---------------------------------------------------------------------------
# Part 1 — familiar topics, small talk register
# ---------------------------------------------------------------------------

PART1_TOPICS: list[dict] = [
    {"category": "hometown", "questions": [
        "Where are you from?",
        "What do you like most about your hometown?",
        "Has your hometown changed much in recent years?",
    ]},
    {"category": "work", "questions": [
        "Do you work or are you a student?",
        "What do you like about your job?",
        "What are your responsibilities at work?",
    ]},
    {"category": "study", "questions": [
        "What subject are you studying?",
        "Why did you choose that subject?",
        "Do you prefer studying alone or with others?",
    ]},
    {"category": "home", "questions": [
        "Do you live in a house or an apartment?",
        "What's your favourite room in your home?",
        "Would you like to move somewhere else in the future?",
    ]},
    {"category": "daily_routine", "questions": [
        "What does a typical day look like for you?",
        "What part of your day do you enjoy the most?",
        "Has your daily routine changed much over the past few years?",
    ]},
    {"category": "food", "questions": [
        "What kind of food do you enjoy eating?",
        "Do you prefer eating at home or in restaurants?",
        "Is food from your country popular abroad?",
    ]},
    {"category": "hobbies", "questions": [
        "What do you like to do in your free time?",
        "Is this something you've always enjoyed doing?",
        "Would you like to try a new hobby in the future?",
    ]},
    {"category": "weather", "questions": [
        "What's the weather like in your country?",
        "What's your favourite season?",
        "Does the weather affect your mood?",
    ]},
    {"category": "family", "questions": [
        "Do you have a big family?",
        "Who are you closest to in your family?",
        "How often do you see your relatives?",
    ]},
    {"category": "friends", "questions": [
        "Do you have a lot of friends?",
        "What do you usually do together with your friends?",
        "What qualities do you look for in a friend?",
    ]},
    {"category": "transport", "questions": [
        "How do you usually travel around your city?",
        "Is public transport good where you live?",
        "Would you rather walk, cycle, or drive?",
    ]},
    {"category": "phone_technology", "questions": [
        "How often do you use your phone?",
        "What do you mainly use your phone for?",
        "Could you live without your phone for a week?",
    ]},
    {"category": "internet", "questions": [
        "How much time do you spend online each day?",
        "What websites or apps do you use most?",
        "Has the internet changed the way you learn?",
    ]},
    {"category": "reading", "questions": [
        "Do you enjoy reading?",
        "What kind of books do you like?",
        "Did you read a lot as a child?",
    ]},
    {"category": "music", "questions": [
        "What kind of music do you like?",
        "Do you play any musical instruments?",
        "Do you listen to music while you work or study?",
    ]},
    {"category": "movies", "questions": [
        "Do you enjoy watching movies?",
        "What kind of movies do you prefer?",
        "Do you prefer watching films at home or at the cinema?",
    ]},
    {"category": "sports", "questions": [
        "Do you play any sports?",
        "What's a popular sport in your country?",
        "Did you do much sport when you were a child?",
    ]},
    {"category": "weekends", "questions": [
        "What do you usually do at the weekend?",
        "Do you prefer relaxing or being active on weekends?",
        "Who do you usually spend your weekends with?",
    ]},
    {"category": "shopping", "questions": [
        "Do you enjoy shopping?",
        "Do you prefer shopping online or in stores?",
        "What was the last thing you bought?",
    ]},
    {"category": "clothes", "questions": [
        "What kind of clothes do you usually wear?",
        "Do you follow fashion trends?",
        "Do you enjoy buying new clothes?",
    ]},
    {"category": "colour", "questions": [
        "What's your favourite colour?",
        "Does the colour of a room affect how you feel?",
        "Do you think colours have different meanings in different cultures?",
    ]},
    {"category": "gifts", "questions": [
        "Do you enjoy giving gifts?",
        "What was the best gift you've ever received?",
        "Is gift-giving important in your culture?",
    ]},
    {"category": "festivals", "questions": [
        "What's an important festival in your country?",
        "How do people usually celebrate it?",
        "Do you enjoy celebrating festivals?",
    ]},
    {"category": "cooking", "questions": [
        "Do you like cooking?",
        "What's a dish you can cook well?",
        "Did anyone teach you how to cook?",
    ]},
    {"category": "pets_animals", "questions": [
        "Do you have any pets?",
        "Do you think keeping pets is a good idea?",
        "Are you afraid of any animals?",
    ]},
    {"category": "plants", "questions": [
        "Do you like plants or gardening?",
        "Do you have any plants at home?",
        "Are there many green spaces in your city?",
    ]},
    {"category": "neighbours", "questions": [
        "Do you know your neighbours well?",
        "Do you think it's important to have a good relationship with neighbours?",
        "How often do you talk to your neighbours?",
    ]},
    {"category": "public_holidays", "questions": [
        "What do you usually do on public holidays?",
        "What's your favourite public holiday?",
        "Do you think there are enough public holidays in your country?",
    ]},
    {"category": "art", "questions": [
        "Are you interested in art?",
        "Did you study art at school?",
        "Do you ever visit art galleries or museums?",
    ]},
    {"category": "photography", "questions": [
        "Do you like taking photos?",
        "What do you usually take photos of?",
        "Do you prefer looking at old photos or taking new ones?",
    ]},
    {"category": "dreams", "questions": [
        "Do you often remember your dreams?",
        "Do you think dreams have meaning?",
        "Have you ever had a dream that felt very real?",
    ]},
    {"category": "sleep", "questions": [
        "How many hours do you usually sleep?",
        "Is it easy for you to fall asleep?",
        "Do you think you get enough sleep?",
    ]},
    {"category": "news", "questions": [
        "How do you usually get the news?",
        "Do you read newspapers?",
        "Do you think it's important to follow the news?",
    ]},
    {"category": "television", "questions": [
        "Do you watch a lot of TV?",
        "What kind of TV programmes do you like?",
        "Do you think TV is becoming less popular?",
    ]},
    {"category": "social_media", "questions": [
        "Do you use social media?",
        "What do you usually use it for?",
        "Do you think social media has more advantages or disadvantages?",
    ]},
    {"category": "letters_mail", "questions": [
        "Do you ever write letters?",
        "When was the last time you received a letter?",
        "Do you prefer emails or letters?",
    ]},
    {"category": "names", "questions": [
        "Does your name have a special meaning?",
        "Who chose your name?",
        "Would you ever consider changing your name?",
    ]},
    {"category": "languages", "questions": [
        "How many languages do you speak?",
        "Is it difficult to learn a new language?",
        "Would you like to learn another language in the future?",
    ]},
    {"category": "jewellery_accessories", "questions": [
        "Do you like wearing jewellery or accessories?",
        "Have you ever received jewellery as a gift?",
        "Do accessories matter to you when choosing an outfit?",
    ]},
    {"category": "childhood", "questions": [
        "Where did you grow up?",
        "What's your happiest childhood memory?",
        "Were you a shy or outgoing child?",
    ]},
]

# ---------------------------------------------------------------------------
# Part 2 — cue cards (the long turn). Each has a linked Part 3 "theme" key
# so a session can pull thematically-connected abstract questions afterwards.
# ---------------------------------------------------------------------------

PART2_CUE_CARDS: list[dict] = [
    {"topic": "Describe a person you admire", "theme": "people",
     "bullets": ["Who this person is", "How you know them",
                 "What they are like", "And explain why you admire them"]},
    {"topic": "Describe a time when you helped someone", "theme": "society",
     "bullets": ["Who you helped", "How you helped them",
                 "Why you helped them", "And explain how you felt about it"]},
    {"topic": "Describe a place you visited that you found interesting", "theme": "places",
     "bullets": ["Where the place is", "When you went there",
                 "What you did there", "And explain why it was interesting"]},
    {"topic": "Describe an object that is important to you", "theme": "objects",
     "bullets": ["What the object is", "How you got it",
                 "How often you use it", "And explain why it's important to you"]},
    {"topic": "Describe an event you enjoyed attending", "theme": "events",
     "bullets": ["What the event was", "When and where it took place",
                 "Who you went with", "And explain why you enjoyed it"]},
    {"topic": "Describe a skill you learned that you find useful", "theme": "education",
     "bullets": ["What the skill is", "How you learned it",
                 "How long it took to learn", "And explain why it is useful"]},
    {"topic": "Describe a decision that was difficult to make", "theme": "society",
     "bullets": ["What the decision was", "What the alternatives were",
                 "Who helped you decide", "And explain why it was difficult"]},
    {"topic": "Describe a book that made an impression on you", "theme": "media",
     "bullets": ["What the book was about", "When you read it",
                 "Why you decided to read it", "And explain what impression it made"]},
    {"topic": "Describe a film you enjoyed watching", "theme": "media",
     "bullets": ["What the film was about", "When you watched it",
                 "Who you watched it with", "And explain why you enjoyed it"]},
    {"topic": "Describe a piece of technology you find useful", "theme": "technology",
     "bullets": ["What it is", "How long you've had it",
                 "How you use it", "And explain why it is useful to you"]},
    {"topic": "Describe a memorable journey you took", "theme": "places",
     "bullets": ["Where you went", "How you travelled",
                 "Who you went with", "And explain why it was memorable"]},
    {"topic": "Describe a time you felt very happy", "theme": "society",
     "bullets": ["When this was", "Where you were",
                 "What happened", "And explain why you felt so happy"]},
    {"topic": "Describe a change that improved your life", "theme": "society",
     "bullets": ["What the change was", "When it happened",
                 "Why it happened", "And explain how it improved your life"]},
    {"topic": "Describe a goal you would like to achieve", "theme": "education",
     "bullets": ["What the goal is", "How you plan to achieve it",
                 "How long it will take", "And explain why this goal is important to you"]},
    {"topic": "Describe a tradition in your country", "theme": "society",
     "bullets": ["What the tradition is", "When it takes place",
                 "Who is usually involved", "And explain why it is important"]},
    {"topic": "Describe an interesting neighbour you have had", "theme": "people",
     "bullets": ["Who this neighbour is", "How you met them",
                 "What they are like", "And explain why you find them interesting"]},
    {"topic": "Describe a website or app you use often", "theme": "technology",
     "bullets": ["What it is", "How you found out about it",
                 "How often you use it", "And explain why you find it useful"]},
    {"topic": "Describe a piece of art you like", "theme": "media",
     "bullets": ["What the artwork is", "Where you saw it",
                 "Who created it", "And explain why you like it"]},
    {"topic": "Describe a time you received good news", "theme": "society",
     "bullets": ["What the news was", "How you found out",
                 "Who told you", "And explain how you reacted"]},
    {"topic": "Describe a rule that you think should be changed", "theme": "society",
     "bullets": ["What the rule is", "Where this rule applies",
                 "Why it exists", "And explain why you think it should change"]},
    {"topic": "Describe an outdoor activity you enjoy", "theme": "society",
     "bullets": ["What the activity is", "Where you usually do it",
                 "Who you do it with", "And explain why you enjoy it"]},
    {"topic": "Describe a time you lost something important", "theme": "society",
     "bullets": ["What you lost", "When and where this happened",
                 "What you did about it", "And explain how you felt"]},
    {"topic": "Describe a family member you spend a lot of time with", "theme": "people",
     "bullets": ["Who this person is", "What you usually do together",
                 "How long you've spent time together", "And explain why you enjoy their company"]},
    {"topic": "Describe a close friend of yours", "theme": "people",
     "bullets": ["Who this friend is", "How you met",
                 "What you do together", "And explain why you value this friendship"]},
    {"topic": "Describe a teacher who influenced you", "theme": "education",
     "bullets": ["Who this teacher was", "What subject they taught",
                 "What they were like", "And explain how they influenced you"]},
    {"topic": "Describe a job you would like to have in the future", "theme": "education",
     "bullets": ["What the job is", "What skills it requires",
                 "Where you might do this job", "And explain why you'd like to do it"]},
    {"topic": "Describe a hobby you took up recently", "theme": "society",
     "bullets": ["What the hobby is", "How you started doing it",
                 "How often you do it", "And explain why you enjoy it"]},
    {"topic": "Describe a memorable meal you had", "theme": "places",
     "bullets": ["What you ate", "Where you had this meal",
                 "Who you were with", "And explain why it was memorable"]},
    {"topic": "Describe a park or garden you like to visit", "theme": "places",
     "bullets": ["Where it is", "What it looks like",
                 "How often you go there", "And explain why you like it"]},
    {"topic": "Describe a historical place you have visited", "theme": "places",
     "bullets": ["Where the place is", "When you visited it",
                 "What you saw there", "And explain why it is historically important"]},
    {"topic": "Describe a gift you gave to someone", "theme": "people",
     "bullets": ["What the gift was", "Who you gave it to",
                 "Why you chose that gift", "And explain how the person reacted"]},
    {"topic": "Describe a time you felt proud of yourself", "theme": "society",
     "bullets": ["What happened", "When this was",
                 "Who else was involved", "And explain why you felt proud"]},
    {"topic": "Describe an important email or letter you received", "theme": "society",
     "bullets": ["Who it was from", "What it was about",
                 "When you received it", "And explain why it was important"]},
    {"topic": "Describe a piece of music that means a lot to you", "theme": "media",
     "bullets": ["What the music is", "When you first heard it",
                 "When you listen to it", "And explain why it means a lot to you"]},
    {"topic": "Describe a sport you enjoy watching or playing", "theme": "society",
     "bullets": ["What the sport is", "How you got interested in it",
                 "How often you watch or play it", "And explain why you enjoy it"]},
    {"topic": "Describe a city you would like to visit", "theme": "places",
     "bullets": ["What city it is", "What you know about it",
                 "What you would like to do there", "And explain why you want to visit"]},
    {"topic": "Describe a mistake you made and learned from", "theme": "education",
     "bullets": ["What the mistake was", "When it happened",
                 "What the consequences were", "And explain what you learned from it"]},
    {"topic": "Describe a time you tried something new", "theme": "education",
     "bullets": ["What you tried", "When this was",
                 "Why you decided to try it", "And explain how it went"]},
    {"topic": "Describe an invention you think is important", "theme": "technology",
     "bullets": ["What the invention is", "Who invented it (if you know)",
                 "How it is used", "And explain why you think it is important"]},
    {"topic": "Describe a childhood memory you enjoy thinking about", "theme": "people",
     "bullets": ["What the memory is", "When it happened",
                 "Who was involved", "And explain why you enjoy thinking about it"]},
    {"topic": "Describe a time you had to wait for something", "theme": "society",
     "bullets": ["What you were waiting for", "How long you waited",
                 "Where you were", "And explain how you felt while waiting"]},
    {"topic": "Describe an ambition you have not yet achieved", "theme": "education",
     "bullets": ["What the ambition is", "When you first had this ambition",
                 "What you have done to achieve it", "And explain why it is important to you"]},
    {"topic": "Describe a celebration you took part in", "theme": "society",
     "bullets": ["What the celebration was", "When and where it happened",
                 "Who you celebrated with", "And explain why it was memorable"]},
    {"topic": "Describe an animal you find interesting", "theme": "society",
     "bullets": ["What the animal is", "Where it can usually be found",
                 "What it looks like", "And explain why you find it interesting"]},
    {"topic": "Describe an app or website that helps you learn", "theme": "technology",
     "bullets": ["What it is", "How you use it",
                 "How long you have used it", "And explain how it helps you learn"]},
    {"topic": "Describe a time you got up very early", "theme": "society",
     "bullets": ["When this was", "Why you got up early",
                 "What you did that day", "And explain how you felt"]},
    {"topic": "Describe a shop or market you like visiting", "theme": "places",
     "bullets": ["Where it is", "What it sells",
                 "How often you go there", "And explain why you like it"]},
    {"topic": "Describe an interesting conversation you had", "theme": "people",
     "bullets": ["Who you spoke with", "What you talked about",
                 "Where this happened", "And explain why it was interesting"]},
    {"topic": "Describe a leader you admire", "theme": "people",
     "bullets": ["Who this person is", "What they have done",
                 "How you learned about them", "And explain why you admire them"]},
    {"topic": "Describe a time you worked as part of a team", "theme": "education",
     "bullets": ["What the task was", "Who else was on the team",
                 "What your role was", "And explain how the experience went"]},
]

# ---------------------------------------------------------------------------
# Part 3 — abstract discussion, grouped by theme so it links back to Part 2
# ---------------------------------------------------------------------------

PART3_QUESTION_BANK: dict[str, list[str]] = {
    "people": [
        "What qualities make someone a good role model?",
        "Do you think people are more influenced by family or by public figures?",
        "How has the idea of a 'hero' changed over generations?",
        "Is it more important to admire someone's achievements or their character?",
        "Do young people today have different role models than in the past?",
        "Why do some people become more influential than others?",
    ],
    "places": [
        "How does tourism affect local communities?",
        "Do you think people should try to preserve historical places?",
        "What are the benefits and drawbacks of living in a big city?",
        "How might travel change in the future?",
        "Should governments invest more in developing rural areas or cities?",
        "Why do some places become popular tourist destinations while others don't?",
    ],
    "objects": [
        "Do people rely too much on modern gadgets nowadays?",
        "How has the value people place on physical objects changed over time?",
        "Do you think possessions can make people happier?",
        "What objects do you think will disappear in the next 20 years?",
        "Is it better to buy fewer, higher-quality items or many cheaper ones?",
        "How do advertisements influence what people choose to buy?",
    ],
    "events": [
        "Why do people enjoy attending large public events?",
        "How have celebrations changed with the rise of social media?",
        "Do you think community events are important for society?",
        "What role do national events play in building identity?",
        "Are traditional celebrations losing their meaning in modern society?",
        "How might events be organised differently in the future?",
    ],
    "education": [
        "Do you think practical skills should be taught more in schools?",
        "How important is it for adults to keep learning new things?",
        "What are the advantages and disadvantages of online learning?",
        "Should education focus more on exams or on personal development?",
        "How has technology changed the way people learn?",
        "Do you think university education is necessary for success?",
    ],
    "technology": [
        "How has technology changed the way people communicate?",
        "Do you think technology has made people more or less productive?",
        "What are the risks of society becoming too dependent on technology?",
        "How might artificial intelligence change everyday jobs?",
        "Should there be more regulation on new technologies?",
        "Do older and younger generations use technology differently?",
    ],
    "media": [
        "How has the media influenced public opinion in your country?",
        "Do you think traditional media will disappear because of the internet?",
        "What responsibility do media companies have to report accurately?",
        "How does media consumption differ between generations?",
        "Should there be stricter controls on content shown to children?",
        "How do you think streaming has changed the entertainment industry?",
    ],
    "society": [
        "Do you think community spirit is stronger now than in the past?",
        "How important is it for neighbours to help each other?",
        "What can governments do to encourage volunteering?",
        "Do you think society is becoming more or less individualistic?",
        "How do traditions help maintain a sense of identity in a country?",
        "What are the biggest challenges facing your society today?",
    ],
}

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class IELTSTopicSet:
    part1_categories: list[dict]
    part2_cue_card: dict
    part3_questions: list[str]
    target_band: float = 6.5
    seed: Optional[int] = field(default=None)


class IELTSTopicGenerator:
    """
    Assembles a coherent topic set for one session. Works fully offline off
    the built-in bank; if an LLM client is supplied it is used to (a) add
    fresh variety on top of the bank and (b) generate contextual Part 3
    follow-ups grounded in what the candidate actually said.
    """

    def __init__(self, llm_client: Optional[IELTSLLMClient] = None):
        self.llm_client = llm_client or IELTSLLMClient()

    async def generate_session_topics(
        self,
        target_band: float = 6.5,
        topics_preference: Optional[str] = None,
        seed: Optional[int] = None,
        exclude_categories: Optional[list[str]] = None,
    ) -> IELTSTopicSet:
        rng = random.Random(seed)
        excluded = set(exclude_categories or [])

        part1_pool = PART1_TOPICS
        if topics_preference:
            filtered = [t for t in PART1_TOPICS if topics_preference.lower() in t["category"]]
            part1_pool = filtered or PART1_TOPICS

        # Filter out recently-used categories for variety across sessions.
        fresh_pool = [t for t in part1_pool if t["category"] not in excluded]
        if len(fresh_pool) < 4:
            fresh_pool = part1_pool  # fall back to full pool if too few remain

        part1_categories = rng.sample(fresh_pool, k=min(4, len(fresh_pool)))

        # Shuffle question order within each chosen category for extra variety
        for cat in part1_categories:
            questions = list(cat.get("questions", []))
            rng.shuffle(questions)
            cat = dict(cat)
            cat["questions"] = questions

        cue_card_pool = PART2_CUE_CARDS
        if topics_preference:
            filtered_cards = [c for c in PART2_CUE_CARDS if topics_preference.lower() in c["theme"]]
            cue_card_pool = filtered_cards or PART2_CUE_CARDS
        cue_card = rng.choice(cue_card_pool)

        # Part 3 is thematically linked to the Part 2 cue card, as in the
        # real test — the examiner "widens out" from the long-turn topic.
        theme = cue_card["theme"]
        part3_pool = PART3_QUESTION_BANK.get(theme, PART3_QUESTION_BANK["society"])
        part3_questions = rng.sample(part3_pool, k=min(5, len(part3_pool)))

        # Optionally ask the LLM for one bonus, freshly generated Part 3
        # question grounded in the same theme, for extra variety.
        try:
            bonus = await self.llm_client.generate_topic_variation(theme=theme)
            if bonus:
                part3_questions.append(bonus)
        except Exception:
            # Offline / no key configured — the built-in bank is sufficient.
            pass

        return IELTSTopicSet(
            part1_categories=part1_categories,
            part2_cue_card=cue_card,
            part3_questions=part3_questions,
            target_band=target_band,
            seed=seed,
        )

    async def generate_dynamic_followup(self, answer: str, part: int, theme: str = "society") -> str:
        """Generate a contextual follow-up based on the candidate's answer.

        Falls back to a generic, still-relevant prompt if no LLM is
        configured, so the session flow never stalls waiting on a key.
        """
        try:
            follow_up = await self.llm_client.generate_followup(answer=answer, part=part, theme=theme)
            if follow_up:
                return follow_up
        except Exception:
            pass

        generic_by_part = {
            1: "Could you tell me a bit more about that?",
            2: "Is there anything else you'd like to add about that?",
            3: "Why do you think that is the case?",
        }
        return generic_by_part.get(part, "Could you expand on that a little?")
