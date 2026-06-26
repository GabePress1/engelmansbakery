# Phase 2 – Customer Invoice Analytics Workflow Crash Analysis

**Date**: June 26, 2026
**Workflow**: Phase 2 – Customer Invoice Analytics (ID: `SjB9N6EAE5MBiuq7`)
**Status**: Deactivated (auto-deactivated due to repeated crashes)

## Executive Summary

The "Phase 2 – Customer Invoice Analytics" workflow has been crashing consistently since June 23, 2026. Analysis of execution logs reveals that the workflow never progresses past the initial Schedule Trigger node, indicating a critical issue with workflow startup or the n8n execution engine itself.

## Execution History

| Date | Execution ID | Duration | Status | Details |
|------|---|---|---|---|
| 2026-06-21 | 640 | 12m 12s | ✅ SUCCESS | Last successful run |
| 2026-06-20 | 637 | 11m 55s | ✅ SUCCESS | Working normally |
| 2026-06-23 | 659 | 11m 54s | ❌ CRASHED | First crash (2-day gap) |
| 2026-06-24 | 750 | 36 sec | ❌ CRASHED | Quick crash (different pattern) |
| 2026-06-25 | 777 | 17m 34s | ❌ CRASHED | Long execution then crash |
| 2026-06-26 | 812 | 14m 50s | ❌ CRASHED | Most recent (still shows running for 14+ min) |

## Key Findings

### 1. Workflow Never Progresses Past Trigger
All crash executions show the **same execution stack**: only the "Schedule Trigger1" node appears in the `nodeExecutionStack`. The workflow never transitions to the first workflow node ("Keys"). This indicates:
- The crash occurs at workflow startup/initialization
- Not a failure within a specific workflow node
- Issue is in the n8n execution engine or workflow loading

### 2. Long Execution Before Crash
Most crashes occur after 10-17 minutes of execution, which is suspicious because:
- The workflow never actually starts (based on nodeExecutionStack analysis)
- 10+ minutes of "nothing" suggests a hang or timeout waiting for something
- The n8n process may be stuck in initialization state

### 3. Sudden Onset (2-Day Gap)
- Last successful run: June 20-21
- First crash: June 23 (2-day gap)
- Suggests an external change or data issue, not a gradual degradation

### 4. Two Types of Crashes
- **Type A** (Execution 750): Very quick crash (~36 sec) - possible immediate error
- **Type B** (Executions 659, 777, 812): Long execution (10-17 min) - possible timeout or resource exhaustion

## Likely Root Causes

### High Priority (Most Likely)
1. **n8n Server Resource Exhaustion**
   - Out of memory causing process to crash
   - High CPU causing timeout
   - Evidence: Long execution time before crash suggests hanging/waiting

2. **Workflow Serialization/Deserialization Issue**
   - Problem loading workflow definition at startup
   - Issue with parsing workflow JSON
   - Causes hang during initialization

3. **Database Connection Issue**
   - n8n unable to fetch workflow from database
   - Connection timeout or database lock
   - Causes workflow to hang during load

### Medium Priority
4. **External Dependency Timeout**
   - The workflow may be loading external configuration
   - An external API call is timing out at startup
   - Evidence: Only visible if workflow has initialization-phase API calls

5. **n8n Version Issue**
   - Recent n8n update broke workflow compatibility
   - Node version mismatch
   - Evidence: Sudden onset correlates with potential update

### Lower Priority
6. **Workflow Logic Error**
   - Despite nodeExecutionStack showing no progress, could be initialization code
   - Evidence: Least likely since stack shows clean trigger state

## Recommended Actions

### Immediate (1-2 hours)
1. **Check n8n System Logs**
   - SSH into n8n server
   - Review `/var/log/n8n/*.log` or container logs
   - Look for OOM (Out of Memory), timeouts, or crashes

2. **Check Server Resources**
   - Monitor CPU, memory, disk during execution time (2:00 AM next schedule)
   - Check if process crashes or gets killed by OOM killer
   - Review n8n's resource limits in Docker/Kubernetes config

3. **Check n8n Version**
   - Verify no automatic updates occurred between June 21-23
   - Check n8n changelog for breaking changes
   - Consider rolling back if recent update detected

### Short-term (Hours)
4. **Try Manual Workflow Execution**
   - Manually trigger the workflow from n8n UI
   - Check real-time error messages in UI
   - Note any error popups or detailed error messages

5. **Check External API Connectivity**
   - Verify BigCommerce API is responding
   - Verify HubSpot API is responding
   - Check credentials (tokens) are valid

6. **Review Workflow Changes**
   - Check if any nodes were modified between June 21-23
   - Check if any node credentials changed
   - Look for recent workflow imports/exports

### Medium-term (Same day)
7. **Isolate the Issue**
   - Disable the "Batch Update HubSpot" node and retry
   - Remove any large data-processing nodes
   - Test workflow with simplified version to isolate which node causes hang

8. **Check n8n Monitoring**
   - Review n8n's built-in metrics if available
   - Check database query logs for slow queries
   - Look for webhook queue backups

9. **File n8n Support Ticket**
   - If local diagnosis is inconclusive
   - Include execution logs and server logs
   - Include workflow JSON export

## Immediate Workaround

While investigating:
1. **Reduce Workflow Scope**: 
   - Duplicate the workflow
   - Remove non-essential nodes
   - Test with smaller data subsets

2. **Add Timeout Protection**:
   - Wrap HTTP calls with explicit timeout values
   - Add error handling to catch timeouts early

3. **Split Workflow**:
   - Break into two smaller workflows
   - Run sequentially or in parallel
   - Reduces memory footprint

## Data to Collect

When accessing n8n:
- Full n8n system logs during next scheduled run (June 27 at 2 AM)
- Workflow JSON export (for backup and analysis)
- System metrics (CPU, memory, disk) during execution
- n8n version number
- Any error messages in n8n UI
- Container/process logs if running in Docker/K8s

## Next Steps

1. **For user (@gpress)**: Access the n8n instance directly and check the workflow execution logs in the UI (click execution → view logs)
2. **Document findings**: Update this file with any error messages found
3. **Implement fix**: Once root cause is identified, implement the appropriate fix
4. **Test**: Re-enable the workflow and monitor next scheduled run (June 27 at 2 AM)
5. **Monitor**: Check next few executions to ensure stability

---

**Analysis Completed**: June 26, 2026
**Analyst**: Claude Code (Workflow Debugging Agent)
**Confidence Level**: Medium (based on API data; would be High with access to system logs)
