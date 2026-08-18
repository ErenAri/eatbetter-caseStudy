# Routes

P7 keeps navigation intentionally small. `App.tsx` owns Today, Capture, Analysis, Meal Review, and
Meal Detail route states. Active backend meal IDs survive ordinary in-app navigation and incomplete
meals can be reopened from Today. File-based routing remains unnecessary for this MVP.
