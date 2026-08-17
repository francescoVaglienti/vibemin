# vibemin — minimize AI-authored changes

After meaningful implementation or test-refactoring work, use the `vibemin` skill to seek a
smaller maintainable patch before reporting completion. Treat behavior, security, test strength,
repository style, and readability as hard constraints. Keep tests outside ordinary production
minimization. Keep dependency metadata and unobserved visuals protected, preserve strict
typechecking, and run final clean-install/lock validation separately. Minimize or merge tests
only with the skill's mutation-testing safeguards.
