#!/usr/bin/Rscript --vanilla

args.vec <- commandArgs(TRUE)
if(length(args.vec) < 4) { stop("Usage: run_dwSSA.R MODEL(character) N(numeric) SEED(numeric) GAMMAS(numeric)") }
model <- args.vec[1]
N <- as.numeric(args.vec[2])
seed <- as.numeric(args.vec[3])
gamma <- as.numeric(args.vec[4:length(args.vec)])

library(cewSSA)
system.time(p <- dwSSA(model=model, gamma=gamma, N=N, seed=seed))
p

