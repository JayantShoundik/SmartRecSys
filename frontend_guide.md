# Frontend ↔ Backend API Contract

## Endpoint

```
POST http://localhost:5000/recommend
Content-Type: application/json
```

## Request Body

```json
{
  "user_id": "Alice",
  "preferences": {
    "domains": ["Web Development", "Programming"],
    "difficulty": "Beginner"
  }
}
```

| Field                   | Type            | Required | Notes                                              |
|-------------------------|-----------------|----------|----------------------------------------------------|
| `user_id`               | string          | Yes      | Student name from login screen                     |
| `preferences.domains`   | array of string | Yes      | One or more of the domain values listed below      |
| `preferences.difficulty`| string          | No       | `"Beginner"`, `"Intermediate"`, `"Advanced"`, or `""` for any |

### Valid domain values
`"Web Development"`, `"Programming"`, `"Data Science"`, `"Machine Learning"`, `"Cybersecurity"`, `"Cloud Computing"`

---

## Response Body

HTTP `200 OK`

```json
[
  {
    "title": "Intro to Python",
    "domain": "Programming",
    "difficulty": "Beginner",
    "score": 0.92
  },
  {
    "title": "React for Beginners",
    "domain": "Web Development",
    "difficulty": "Beginner",
    "score": 0.87
  }
]
```

| Field        | Type   | Notes                                      |
|--------------|--------|--------------------------------------------|
| `title`      | string | Course name                                |
| `domain`     | string | Must match one of the valid domain values  |
| `difficulty` | string | `"Beginner"`, `"Intermediate"`, or `"Advanced"` |
| `score`      | float  | Relevance score between `0.0` and `1.0`    |

---

## Error Response

```json
{ "error": "description of what went wrong" }
```

HTTP status codes: `400` for bad input, `500` for server errors.

---

## CORS

The Flask/FastAPI backend must allow `http://localhost` (or `*` during development):

```python
# Flask example
from flask_cors import CORS
CORS(app)
```

---

## Switching from Mock to Real API

In `frontend/app.js`, inside `fetchRecommendations()`:

1. Delete the mock `return` statement
2. Uncomment the `fetch(...)` block
3. Update the URL if the backend runs on a different port
