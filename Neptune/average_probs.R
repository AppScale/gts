#!/usr/bin/Rscript --vanilla

args.vec <- commandArgs(TRUE)
if(length(args.vec) < 1) { stop("Usage: average_probs.R FILE(S)(character)") }
file.vec <- args.vec

# Initialize vars
nprobs <- 4
prob.mat <- numeric(0)

# Populate result matrix
for(file in file.vec) {
  prob <- system(paste("tail -n1 ", file, sep=""), intern=T)
  prob <- unlist(strsplit(prob, split=" "))
  prob.mat <- rbind(prob.mat, as.numeric(prob[(length(prob)-nprobs+1):length(prob)]))
}

# Combine results
N <- prob.mat[,1]
m1 <- prob.mat[,3]*N
sigma2 <- prob.mat[,4]^2*N
m2 <- (sigma2+(m1/N)^2)*N

M1overN <- sum(m1)/sum(N)
M2overN <- sum(m2)/sum(N)
Sigma2 <- M2overN - M1overN^2
SE <- sqrt(Sigma2/sum(N))

# Output results
cat(paste(M1overN," +/- ",SE,"\n", sep=""))

