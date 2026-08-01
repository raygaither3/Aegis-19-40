# 2026-07-30

## Goal

Build the first signal detector.

## Problem

How do we determine what constitutes a signal?

## Solution

Estimate the noise floor using the median.

Bins 10 dB above the noise floor are considered active.

## Results

Successfully detected one simulated signal.

## Questions

What happens if there are two signals?

How do we reject false positives?