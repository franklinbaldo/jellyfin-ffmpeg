/* SPDX-License-Identifier: LGPL-2.1-or-later */
#ifndef LEGACY390_PROFILE_H
#define LEGACY390_PROFILE_H
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
typedef struct Legacy390Metric { const char *name; unsigned long calls; double total,max,first10,first50; } Legacy390Metric;
static Legacy390Metric legacy390_metrics[64];
static pthread_mutex_t legacy390_lock=PTHREAD_MUTEX_INITIALIZER;
static int legacy390_registered;
static double legacy390_now(void) {
 struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
 return t.tv_sec+t.tv_nsec*1e-9;
}
static void legacy390_dump(void) {
 for(int i=0;i<64;i++) if(legacy390_metrics[i].name)
  fprintf(stderr,"LEGACY390_PROFILE %s | %s | calls=%lu total_ms=%.3f max_ms=%.3f first10_ms=%.3f first50_ms=%.3f\n",
   LEGACY390_UNIT,legacy390_metrics[i].name,legacy390_metrics[i].calls,
   legacy390_metrics[i].total*1000,legacy390_metrics[i].max*1000,legacy390_metrics[i].first10*1000,legacy390_metrics[i].first50*1000);
}
static void legacy390_record(const char *name,double elapsed) {
 pthread_mutex_lock(&legacy390_lock);
 if(!legacy390_registered) { atexit(legacy390_dump); legacy390_registered=1; }
 for(int i=0;i<64;i++) {
  Legacy390Metric *m=&legacy390_metrics[i];
  if(!m->name) m->name=name;
  if(!strcmp(m->name,name)) {
   m->calls++; m->total+=elapsed; if(m->calls<=10)m->first10+=elapsed; if(m->calls<=50)m->first50+=elapsed; if(elapsed>m->max)m->max=elapsed; break;
  }
 }
 pthread_mutex_unlock(&legacy390_lock);
}
#define LEGACY390_MEASURE(expr, call) ({ \
 int legacy390_on=getenv("LEGACY390_PROFILE")!=NULL; \
 double legacy390_start=legacy390_on?legacy390_now():0; \
 int legacy390_result=(expr); \
 if(legacy390_on)legacy390_record(call,legacy390_now()-legacy390_start); \
 legacy390_result; })
#endif
