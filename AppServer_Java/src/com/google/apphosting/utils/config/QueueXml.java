package com.google.apphosting.utils.config;

import com.google.apphosting.utils.config.AppEngineConfigException;
import java.util.Collection;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class QueueXml {
   static final String RATE_REGEX = "([0-9]+(\\.[0-9]+)?)/([smhd])";
   static final Pattern RATE_PATTERN = Pattern.compile("([0-9]+(\\.[0-9]+)?)/([smhd])");
   static final String TOTAL_STORAGE_LIMIT_REGEX = "^([0-9]+(\\.[0-9]*)?[BKMGT]?)";
   static final Pattern TOTAL_STORAGE_LIMIT_PATTERN = Pattern.compile("^([0-9]+(\\.[0-9]*)?[BKMGT]?)");
   private static final int MAX_QUEUE_NAME_LENGTH = 100;
   private static final String QUEUE_NAME_REGEX = "[a-zA-Z\\d-]{1,100}";
   private static final Pattern QUEUE_NAME_PATTERN = Pattern.compile("[a-zA-Z\\d-]{1,100}");
   private static final String TASK_AGE_LIMIT_REGEX = "([0-9]+(?:\\.?[0-9]*(?:[eE][\\-+]?[0-9]+)?)?)([smhd])";
   private static final Pattern TASK_AGE_LIMIT_PATTERN = Pattern.compile("([0-9]+(?:\\.?[0-9]*(?:[eE][\\-+]?[0-9]+)?)?)([smhd])");
   private static final String MODE_REGEX = "push|pull";
   private static final Pattern MODE_PATTERN = Pattern.compile("push|pull");
   private static final int MAX_TARGET_LENGTH = 100;
   private static final String TARGET_REGEX = "[a-z\\d\\-\\.]{1,100}";
   private static final Pattern TARGET_PATTERN = Pattern.compile("[a-z\\d\\-\\.]{1,100}");
   private static final String DEFAULT_QUEUE = "default";
   private final LinkedHashMap entries = new LinkedHashMap();
   private QueueXml.Entry lastEntry;
   private String totalStorageLimit = "";

   public static QueueXml.Entry defaultEntry() {
      return new QueueXml.Entry("default", 5.0D, QueueXml.RateUnit.SECOND, 5, (Integer)null, (String)null);
   }

   public QueueXml.Entry addNewEntry() {
      this.validateLastEntry();
      this.lastEntry = new QueueXml.Entry();
      return this.lastEntry;
   }

   public void addEntry(QueueXml.Entry entry) {
      this.validateLastEntry();
      this.lastEntry = entry;
      this.validateLastEntry();
   }

   public Collection<QueueXml.Entry> getEntries() {
      this.validateLastEntry();
      return this.entries.values();
   }

   public void validateLastEntry() {
      if(this.lastEntry != null) {
         if(this.lastEntry.getName() == null) {
            throw new AppEngineConfigException("Queue entry must have a name.");
         } else if(this.entries.containsKey(this.lastEntry.getName())) {
            throw new AppEngineConfigException("Queue entry has duplicate name.");
         } else {
            if("pull".equals(this.lastEntry.getMode())) {
               if(this.lastEntry.getRate() != null) {
                  throw new AppEngineConfigException("Rate must not be specified for pull queue.");
               }

               if(this.lastEntry.getBucketSize() != null) {
                  throw new AppEngineConfigException("Bucket size must not be specified for pull queue.");
               }

               if(this.lastEntry.getMaxConcurrentRequests() != null) {
                  throw new AppEngineConfigException("MaxConcurrentRequests must not be specified for pull queue.");
               }

               QueueXml.RetryParameters retryParameters = this.lastEntry.getRetryParameters();
               if(retryParameters != null) {
                  if(retryParameters.getAgeLimitSec() != null) {
                     throw new AppEngineConfigException("Age limit must not be specified for pull queue.");
                  }

                  if(retryParameters.getMinBackoffSec() != null) {
                     throw new AppEngineConfigException("Min backoff must not be specified for pull queue.");
                  }

                  if(retryParameters.getMaxBackoffSec() != null) {
                     throw new AppEngineConfigException("Max backoff must not be specified for pull queue.");
                  }

                  if(retryParameters.getMaxDoublings() != null) {
                     throw new AppEngineConfigException("Max doublings must not be specified for pull queue.");
                  }
               }
            } else if(this.lastEntry.getRate() == null) {
               throw new AppEngineConfigException("A queue rate is required for push queue.");
            }

            this.entries.put(this.lastEntry.getName(), this.lastEntry);
            this.lastEntry = null;
         }
      }
   }

   public void setTotalStorageLimit(String s) {
      this.totalStorageLimit = s;
   }

   public String getTotalStorageLimit() {
      return this.totalStorageLimit;
   }

   public String toYaml() {
      StringBuilder builder = new StringBuilder();
      if(this.getTotalStorageLimit().length() > 0) {
         builder.append("total_storage_limit: " + this.getTotalStorageLimit() + "\n\n");
      }

      builder.append("queue:\n");
      Iterator i$ = this.getEntries().iterator();

      while(true) {
         List acl;
         do {
            if(!i$.hasNext()) {
               return builder.toString();
            }

            QueueXml.Entry ent = (QueueXml.Entry)i$.next();
            builder.append("- name: " + ent.getName() + "\n");
            Double rate = ent.getRate();
            if(rate != null) {
               builder.append("  rate: " + rate + '/' + ent.getRateUnit().getIdent() + "\n");
            }

            Integer bucketSize = ent.getBucketSize();
            if(bucketSize != null) {
               builder.append("  bucket_size: " + bucketSize + "\n");
            }

            Integer maxConcurrentRequests = ent.getMaxConcurrentRequests();
            if(maxConcurrentRequests != null) {
               builder.append("  max_concurrent_requests: " + maxConcurrentRequests + "\n");
            }

            QueueXml.RetryParameters retryParameters = ent.getRetryParameters();
            if(retryParameters != null) {
               builder.append("  retry_parameters:\n");
               if(retryParameters.getRetryLimit() != null) {
                  builder.append("    task_retry_limit: " + retryParameters.getRetryLimit() + "\n");
               }

               if(retryParameters.getAgeLimitSec() != null) {
                  builder.append("    task_age_limit: " + retryParameters.getAgeLimitSec() + "s\n");
               }

               if(retryParameters.getMinBackoffSec() != null) {
                  builder.append("    min_backoff_seconds: " + retryParameters.getMinBackoffSec() + "\n");
               }

               if(retryParameters.getMaxBackoffSec() != null) {
                  builder.append("    max_backoff_seconds: " + retryParameters.getMaxBackoffSec() + "\n");
               }

               if(retryParameters.getMaxDoublings() != null) {
                  builder.append("    max_doublings: " + retryParameters.getMaxDoublings() + "\n");
               }
            }

            String target = ent.getTarget();
            if(target != null) {
               builder.append("  target: " + target + "\n");
            }

            String mode = ent.getMode();
            if(mode != null) {
               builder.append("  mode: " + mode + "\n");
            }

            acl = ent.getAcl();
         } while(acl == null);

         builder.append("  acl:\n");
         Iterator i$1 = acl.iterator();

         while(i$1.hasNext()) {
            QueueXml.AclEntry aclEntry = (QueueXml.AclEntry)i$1.next();
            if(aclEntry.getUserEmail() != null) {
               builder.append("  - user_email: " + aclEntry.getUserEmail() + "\n");
            } else if(aclEntry.getWriterEmail() != null) {
               builder.append("  - writer_email: " + aclEntry.getWriterEmail() + "\n");
            }
         }
      }
   }

   public static class Entry {
      private String name;
      private Double rate;
      private QueueXml.RateUnit rateUnit;
      private Integer bucketSize;
      private Integer maxConcurrentRequests;
      private QueueXml.RetryParameters retryParameters;
      private String target;
      private String mode;
      private List acl;

      public Entry() {
         this.name = null;
         this.rate = null;
         this.rateUnit = QueueXml.RateUnit.SECOND;
         this.bucketSize = null;
         this.maxConcurrentRequests = null;
         this.retryParameters = null;
         this.target = null;
         this.mode = null;
         this.acl = null;
      }

      public Entry(String name, double rate, QueueXml.RateUnit rateUnit, int bucketSize, Integer maxConcurrentRequests, String target) {
         this.name = name;
         this.rate = Double.valueOf(rate);
         this.rateUnit = rateUnit;
         this.bucketSize = Integer.valueOf(bucketSize);
         this.maxConcurrentRequests = maxConcurrentRequests;
         this.target = target;
      }

      public String getName() {
         return this.name;
      }

      public void setName(String queueName) {
         if(queueName != null && queueName.length() != 0 && QueueXml.QUEUE_NAME_PATTERN.matcher(queueName).matches()) {
            this.name = queueName;
         } else {
            throw new AppEngineConfigException("Queue name does not match expression " + QueueXml.QUEUE_NAME_PATTERN + "; found \'" + queueName + "\'");
         }
      }

      public void setMode(String mode) {
         if(mode != null && mode.length() != 0 && QueueXml.MODE_PATTERN.matcher(mode).matches()) {
            this.mode = mode;
         } else {
            throw new AppEngineConfigException("mode must be either \'push\' or \'pull\'");
         }
      }

      public String getMode() {
         return this.mode;
      }

      public List getAcl() {
         return this.acl;
      }

      public void setAcl(List acl) {
         this.acl = acl;
      }

      public void addAcl(QueueXml.AclEntry aclEntry) {
         this.acl.add(aclEntry);
      }

      public Double getRate() {
         return this.rate;
      }

      public void setRate(double rate) {
         this.rate = Double.valueOf(rate);
      }

      public void setRate(String rateString) {
         if(rateString.equals("0")) {
            this.rate = Double.valueOf(0.0D);
            this.rateUnit = QueueXml.RateUnit.SECOND;
         } else {
            Matcher matcher = QueueXml.RATE_PATTERN.matcher(rateString);
            if(!matcher.matches()) {
               throw new AppEngineConfigException("Invalid queue rate was specified.");
            } else {
               String digits = matcher.group(1);
               this.rateUnit = QueueXml.RateUnit.valueOf(matcher.group(3).charAt(0));
               this.rate = Double.valueOf(digits);
            }
         }
      }

      public QueueXml.RateUnit getRateUnit() {
         return this.rateUnit;
      }

      public void setRateUnit(QueueXml.RateUnit rateUnit) {
         this.rateUnit = rateUnit;
      }

      public Integer getBucketSize() {
         return this.bucketSize;
      }

      public void setBucketSize(int bucketSize) {
         this.bucketSize = Integer.valueOf(bucketSize);
      }

      public void setBucketSize(String bucketSize) {
         try {
            this.bucketSize = Integer.valueOf(bucketSize);
         } catch (NumberFormatException var3) {
            throw new AppEngineConfigException("Invalid bucket-size was specified.", var3);
         }
      }

      public Integer getMaxConcurrentRequests() {
         return this.maxConcurrentRequests;
      }

      public void setMaxConcurrentRequests(int maxConcurrentRequests) {
         this.maxConcurrentRequests = Integer.valueOf(maxConcurrentRequests);
      }

      public void setMaxConcurrentRequests(String maxConcurrentRequests) {
         try {
            this.maxConcurrentRequests = Integer.valueOf(maxConcurrentRequests);
         } catch (NumberFormatException var3) {
            throw new AppEngineConfigException("Invalid max-concurrent-requests was specified: \'" + maxConcurrentRequests + "\'", var3);
         }
      }

      public QueueXml.RetryParameters getRetryParameters() {
         return this.retryParameters;
      }

      public void setRetryParameters(QueueXml.RetryParameters retryParameters) {
         this.retryParameters = retryParameters;
      }

      public String getTarget() {
         return this.target;
      }

      public void setTarget(String target) {
         Matcher matcher = QueueXml.TARGET_PATTERN.matcher(target);
         if(!matcher.matches()) {
            throw new AppEngineConfigException("Invalid queue target was specified. Target: \'" + target + "\'");
         } else {
            this.target = target;
         }
      }

      public int hashCode() {
         boolean prime = true;
         byte result = 1;
         int result1 = 31 * result + (this.acl == null?0:this.acl.hashCode());
         result1 = 31 * result1 + (this.bucketSize == null?0:this.bucketSize.hashCode());
         result1 = 31 * result1 + (this.maxConcurrentRequests == null?0:this.maxConcurrentRequests.hashCode());
         result1 = 31 * result1 + (this.mode == null?0:this.mode.hashCode());
         result1 = 31 * result1 + (this.name == null?0:this.name.hashCode());
         result1 = 31 * result1 + (this.rate == null?0:this.rate.hashCode());
         result1 = 31 * result1 + (this.rateUnit == null?0:this.rateUnit.hashCode());
         result1 = 31 * result1 + (this.target == null?0:this.target.hashCode());
         result1 = 31 * result1 + (this.retryParameters == null?0:this.retryParameters.hashCode());
         return result1;
      }

      public boolean equals(Object obj) {
         if(this == obj) {
            return true;
         } else if(obj == null) {
            return false;
         } else if(this.getClass() != obj.getClass()) {
            return false;
         } else {
            QueueXml.Entry other = (QueueXml.Entry)obj;
            if(this.acl == null) {
               if(other.acl != null) {
                  return false;
               }
            } else if(!this.acl.equals(other.acl)) {
               return false;
            }

            if(this.bucketSize == null) {
               if(other.bucketSize != null) {
                  return false;
               }
            } else if(!this.bucketSize.equals(other.bucketSize)) {
               return false;
            }

            if(this.maxConcurrentRequests == null) {
               if(other.maxConcurrentRequests != null) {
                  return false;
               }
            } else if(!this.maxConcurrentRequests.equals(other.maxConcurrentRequests)) {
               return false;
            }

            if(this.mode == null) {
               if(other.mode != null) {
                  return false;
               }
            } else if(!this.mode.equals(other.mode)) {
               return false;
            }

            if(this.name == null) {
               if(other.name != null) {
                  return false;
               }
            } else if(!this.name.equals(other.name)) {
               return false;
            }

            if(this.rate == null) {
               if(other.rate != null) {
                  return false;
               }
            } else if(!this.rate.equals(other.rate)) {
               return false;
            }

            if(this.rateUnit == null) {
               if(other.rateUnit != null) {
                  return false;
               }
            } else if(!this.rateUnit.equals(other.rateUnit)) {
               return false;
            }

            if(this.target == null) {
               if(other.target != null) {
                  return false;
               }
            } else if(!this.target.equals(other.target)) {
               return false;
            }

            if(this.retryParameters == null) {
               if(other.retryParameters != null) {
                  return false;
               }
            } else if(!this.retryParameters.equals(other.retryParameters)) {
               return false;
            }

            return true;
         }
      }
   }

   public static class RetryParameters {
      private Integer retryLimit = null;
      private Integer ageLimitSec = null;
      private Double minBackoffSec = null;
      private Double maxBackoffSec = null;
      private Integer maxDoublings = null;

      public Integer getRetryLimit() {
         return this.retryLimit;
      }

      public void setRetryLimit(int retryLimit) {
         this.retryLimit = Integer.valueOf(retryLimit);
      }

      public void setRetryLimit(String retryLimit) {
         this.retryLimit = Integer.valueOf(retryLimit);
      }

      public Integer getAgeLimitSec() {
         return this.ageLimitSec;
      }

      public void setAgeLimitSec(String ageLimitString) {
         Matcher matcher = QueueXml.TASK_AGE_LIMIT_PATTERN.matcher(ageLimitString);
         if(matcher.matches() && matcher.groupCount() == 2) {
            double rateUnitSec = (double)QueueXml.RateUnit.valueOf(matcher.group(2).charAt(0)).getSeconds();
            Double ageLimit = Double.valueOf(Double.valueOf(matcher.group(1)).doubleValue() * rateUnitSec);
            this.ageLimitSec = Integer.valueOf(ageLimit.intValue());
         } else {
            throw new AppEngineConfigException("Invalid task age limit was specified.");
         }
      }

      public Double getMinBackoffSec() {
         return this.minBackoffSec;
      }

      public void setMinBackoffSec(double minBackoffSec) {
         this.minBackoffSec = Double.valueOf(minBackoffSec);
      }

      public void setMinBackoffSec(String minBackoffSec) {
         this.minBackoffSec = Double.valueOf(minBackoffSec);
      }

      public Double getMaxBackoffSec() {
         return this.maxBackoffSec;
      }

      public void setMaxBackoffSec(double maxBackoffSec) {
         this.maxBackoffSec = Double.valueOf(maxBackoffSec);
      }

      public void setMaxBackoffSec(String maxBackoffSec) {
         this.maxBackoffSec = Double.valueOf(maxBackoffSec);
      }

      public Integer getMaxDoublings() {
         return this.maxDoublings;
      }

      public void setMaxDoublings(int maxDoublings) {
         this.maxDoublings = Integer.valueOf(maxDoublings);
      }

      public void setMaxDoublings(String maxDoublings) {
         this.maxDoublings = Integer.valueOf(maxDoublings);
      }

      public int hashCode() {
         boolean prime = true;
         byte result = 1;
         int result1 = 31 * result + (this.ageLimitSec == null?0:this.ageLimitSec.hashCode());
         result1 = 31 * result1 + (this.maxBackoffSec == null?0:this.maxBackoffSec.hashCode());
         result1 = 31 * result1 + (this.maxDoublings == null?0:this.maxDoublings.hashCode());
         result1 = 31 * result1 + (this.minBackoffSec == null?0:this.minBackoffSec.hashCode());
         result1 = 31 * result1 + (this.retryLimit == null?0:this.retryLimit.hashCode());
         return result1;
      }

      public boolean equals(Object obj) {
         if(this == obj) {
            return true;
         } else if(obj == null) {
            return false;
         } else if(this.getClass() != obj.getClass()) {
            return false;
         } else {
            QueueXml.RetryParameters other = (QueueXml.RetryParameters)obj;
            if(this.ageLimitSec == null) {
               if(other.ageLimitSec != null) {
                  return false;
               }
            } else if(!this.ageLimitSec.equals(other.ageLimitSec)) {
               return false;
            }

            if(this.maxBackoffSec == null) {
               if(other.maxBackoffSec != null) {
                  return false;
               }
            } else if(!this.maxBackoffSec.equals(other.maxBackoffSec)) {
               return false;
            }

            if(this.maxDoublings == null) {
               if(other.maxDoublings != null) {
                  return false;
               }
            } else if(!this.maxDoublings.equals(other.maxDoublings)) {
               return false;
            }

            if(this.minBackoffSec == null) {
               if(other.minBackoffSec != null) {
                  return false;
               }
            } else if(!this.minBackoffSec.equals(other.minBackoffSec)) {
               return false;
            }

            if(this.retryLimit == null) {
               if(other.retryLimit != null) {
                  return false;
               }
            } else if(!this.retryLimit.equals(other.retryLimit)) {
               return false;
            }

            return true;
         }
      }
   }

   public static class AclEntry {
      private String userEmail = null;
      private String writerEmail = null;

      public void setUserEmail(String userEmail) {
         this.userEmail = userEmail;
      }

      public String getUserEmail() {
         return this.userEmail;
      }

      public void setWriterEmail(String writerEmail) {
         this.writerEmail = writerEmail;
      }

      public String getWriterEmail() {
         return this.writerEmail;
      }

      public int hashCode() {
         boolean prime = true;
         byte result = 1;
         int result1 = 31 * result + (this.userEmail == null?0:this.userEmail.hashCode());
         result1 = 31 * result1 + (this.writerEmail == null?0:this.writerEmail.hashCode());
         return result1;
      }

      public boolean equals(Object obj) {
         if(this == obj) {
            return true;
         } else if(obj == null) {
            return false;
         } else if(this.getClass() != obj.getClass()) {
            return false;
         } else {
            QueueXml.AclEntry other = (QueueXml.AclEntry)obj;
            if(this.userEmail == null) {
               if(other.userEmail != null) {
                  return false;
               }
            } else if(!this.userEmail.equals(other.userEmail)) {
               return false;
            }

            if(this.writerEmail == null) {
               if(other.writerEmail != null) {
                  return false;
               }
            } else if(!this.writerEmail.equals(other.writerEmail)) {
               return false;
            }

            return true;
         }
      }
   }

   public static enum RateUnit {
      SECOND('s', 1),
      MINUTE('m', SECOND.getSeconds() * 60),
      HOUR('h', MINUTE.getSeconds() * 60),
      DAY('d', HOUR.getSeconds() * 24);

      final char ident;
      final int seconds;

      private RateUnit(char ident, int seconds) {
         this.ident = ident;
         this.seconds = seconds;
      }

      static QueueXml.RateUnit valueOf(char unit) {
         switch(unit) {
         case 'd':
            return DAY;
         case 'h':
            return HOUR;
         case 'm':
            return MINUTE;
         case 's':
            return SECOND;
         default:
            throw new AppEngineConfigException("Invalid rate was specified.");
         }
      }

      public char getIdent() {
         return this.ident;
      }

      public int getSeconds() {
         return this.seconds;
      }
   }
}
