TABLE users
------
id (UUID, PK)
email (unique)
password_hash
role (parent)

created_at
last_login


TABLE child_profiles
--------------
id (UUID, PK)
user_id (FK → users.id)

name (optional)
year_group (3–6)
exam_goal (11_plus | sats | both)

confidence_level (low | medium | high)

created_at


TABLE learning_sessions
-----------------
id (UUID, PK)
user_id (FK)
child_profile_id (FK)

mode (homework | eleven_plus | sats | practice)

started_at
ended_at


TABLE session_messages
----------------
id (UUID, PK)
session_id (FK)

sender (user | ai)

content (text)
message_type (question | explanation | hint | answer)

metadata (JSON)  -- stores difficulty, topic, etc.

created_at


TABLE questions
---------
id (UUID, PK)

subject (math | english | reasoning)
exam_type (11_plus | sats | homework)

year_group (3-6)
difficulty (1-5)

question_text
correct_answer
explanation

tags (JSON array)
created_at

TABLE user_answers
------------
id (UUID, PK)

user_id (FK)
child_profile_id (FK)
question_id (FK)

user_answer
is_correct (boolean)

attempt_time
time_taken_seconds


TABLE progress_summary
---------------
id (UUID, PK)

child_profile_id (FK)

subject (math | english | reasoning)

questions_attempted
correct_answers
accuracy_rate

weak_topics (JSON)
strong_topics (JSON)

updated_at


TABLE topic_progress
--------------
id (UUID, PK)

child_profile_id (FK)

topic (fractions | grammar | vocabulary | etc)

attempted
correct
accuracy


TABLE subscriptions
-------------
id (UUID, PK)

user_id (FK)

plan (free | starter | core | premium)

status (active | cancelled | trialing)

start_date
end_date

stripe_customer_id
stripe_subscription_id


TABLE paywall_events
--------------
id (UUID, PK)

user_id
child_profile_id

event_type (
  explanation_locked,
  practice_locked,
  mock_test_locked,
  upgrade_prompt_shown
)

context (JSON)

created_at


TABLE generated_questions
-------------------
id (UUID, PK)

prompt_hash
question_text
answer
explanation

subject
year_group
exam_type

created_at


TABLE events
------
id (UUID, PK)

user_id
child_profile_id

event_name (
  question_started,
  question_completed,
  upgrade_clicked,
  subscription_started
)

metadata (JSON)

created_at


RELATIONSHIPS BETWEEN TABLES
users
  ├── child_profiles
  │       ├── learning_sessions
  │       │        ├── session_messages
  │       │
  │       ├── user_answers
  │       ├── progress_summary
  │       └── topic_progress
  │
  ├── subscriptions
  └── paywall_events