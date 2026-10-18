"""Decision engine — ranks candidate mandis by expected net realization
after freight, spoilage, and mandi deductions.

This module is intentionally free of ML. The spoilage model is a
deterministic Q10 decay integrator seeded from USDA AH-66 shelf-life
values, and the freight model is the seed-value linear model in
`backend.cost`. Both are labelled as *estimates* in every response.
"""
