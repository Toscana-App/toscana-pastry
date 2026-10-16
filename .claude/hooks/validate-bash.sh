#!/bin/bash
# Simple hook to prevent pushing secrets
if git diff --staged | grep -qE '(sk-|AIza|xox|ghp_|AKIA|BEGIN.*PRIVATE KEY)'; then
  echo 'Error: Potential secret detected!'
  exit 1
fi