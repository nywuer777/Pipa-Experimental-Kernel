// C / Linux 4.19 ARM64 QEMU guest / PREEMPT_RT two-kthread spinlock_t contention and sleep / NO FLASH
#include <linux/completion.h>
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/err.h>
#include <linux/init.h>
#include <linux/interrupt.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/kthread.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/preempt.h>
#include <linux/sched.h>
#include <linux/spinlock.h>

#define EXP76_SLEEP_MS          40
#define EXP76_MIN_WAIT_US       30000LL
#define EXP76_HANDSHAKE_MS      1500
#define EXP76_WORKER_MS         3500

#ifdef CONFIG_PREEMPT_RT_FULL
static DEFINE_SPINLOCK(exp76_lock);
static DECLARE_COMPLETION(exp76_t1_held);
static DECLARE_COMPLETION(exp76_t2_attempting);
static DECLARE_COMPLETION(exp76_t1_done);
static DECLARE_COMPLETION(exp76_t2_done);
static struct task_struct *exp76_t1;
static struct task_struct *exp76_t2;
static bool exp76_t1_releasing;
static s64 exp76_t1_sleep_us;
static s64 exp76_t2_wait_us;
static int exp76_t1_rc;
static int exp76_t2_rc;

/* Keep tasks alive until kthread_stop() joins them: no stale task_struct. */
static void exp76_park_until_stop(void)
{
    for (;;) {
        set_current_state(TASK_INTERRUPTIBLE);
        if (kthread_should_stop())
            break;
        schedule();
    }
    __set_current_state(TASK_RUNNING);
}

static int exp76_owner(void *unused)
{
    ktime_t before;
    int rc = 0;

    spin_lock(&exp76_lock);
    pr_info("EXP76_RT_SPIN_SLEEP T1_HELD\n");
    complete(&exp76_t1_held);

    if (!wait_for_completion_timeout(&exp76_t2_attempting,
                                     msecs_to_jiffies(EXP76_HANDSHAKE_MS))) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_T2_HANDSHAKE_TIMEOUT\n");
        rc = -ETIMEDOUT;
        goto out_unlock;
    }

    if (!preemptible() || irqs_disabled()) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_PREEMPTION_DISABLED\n");
        rc = -EINVAL;
        goto out_unlock;
    }

    might_sleep();
    before = ktime_get();
    msleep(EXP76_SLEEP_MS);
    exp76_t1_sleep_us = ktime_to_us(ktime_sub(ktime_get(), before));
    if (exp76_t1_sleep_us < EXP76_MIN_WAIT_US) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_T1_SLEEP_SHORT us=%lld\n",
               (long long)exp76_t1_sleep_us);
        rc = -EIO;
    }

out_unlock:
    /* Mark release before unlock; t2 reads marker after its lock acquire. */
    WRITE_ONCE(exp76_t1_releasing, true);
    spin_unlock(&exp76_lock);
    pr_info("EXP76_RT_SPIN_SLEEP T1_RELEASED\n");

    WRITE_ONCE(exp76_t1_rc, rc);
    complete(&exp76_t1_done);
    exp76_park_until_stop();
    return rc;
}

static int exp76_contender(void *unused)
{
    ktime_t begin, acquired;
    bool saw_release;
    int rc = 0;

    if (!wait_for_completion_timeout(&exp76_t1_held,
                                     msecs_to_jiffies(EXP76_HANDSHAKE_MS))) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_T1_HANDSHAKE_TIMEOUT\n");
        rc = -ETIMEDOUT;
        goto out_done;
    }

    /*
     * begin precedes signaling t1, and t1 waits for this signal before
     * sleeping. t2 must therefore attempt acquisition during t1 ownership.
     */
    begin = ktime_get();
    pr_info("EXP76_RT_SPIN_SLEEP T2_ATTEMPT\n");
    complete(&exp76_t2_attempting);

    spin_lock(&exp76_lock);
    acquired = ktime_get();
    saw_release = READ_ONCE(exp76_t1_releasing);
    spin_unlock(&exp76_lock);

    exp76_t2_wait_us = ktime_to_us(ktime_sub(acquired, begin));
    if (!saw_release) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_SERIALIZATION_EARLY wait_us=%lld\n",
               (long long)exp76_t2_wait_us);
        rc = -EINVAL;
    } else if (exp76_t2_wait_us < EXP76_MIN_WAIT_US) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_SERIALIZATION_SHORT wait_us=%lld\n",
               (long long)exp76_t2_wait_us);
        rc = -EIO;
    } else {
        pr_info("EXP76_RT_SPIN_SLEEP CONTENTION_PASS wait_us=%lld release_seen=1\n",
                (long long)exp76_t2_wait_us);
    }

out_done:
    WRITE_ONCE(exp76_t2_rc, rc);
    complete(&exp76_t2_done);
    exp76_park_until_stop();
    return rc;
}
#endif

static int __init exp76_spin_sleep_init(void)
{
#ifndef CONFIG_PREEMPT_RT_FULL
    pr_err("EXP76_RT_SPIN_SLEEP BLOCKED_CONFIG PREEMPT_RT_FULL=n\n");
    return -EOPNOTSUPP;
#else
    unsigned long done_t1, done_t2;
    int rc;

    pr_info("EXP76_RT_SPIN_SLEEP BEGIN test_id=EXP76_RT_SPIN_SLEEP_QEMU_V2\n");

    exp76_t1 = kthread_run(exp76_owner, NULL, "exp76_rt_owner");
    if (IS_ERR(exp76_t1)) {
        rc = PTR_ERR(exp76_t1);
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_CREATE_T1 rc=%d\n", rc);
        return rc;
    }

    exp76_t2 = kthread_run(exp76_contender, NULL, "exp76_rt_contender");
    if (IS_ERR(exp76_t2)) {
        rc = PTR_ERR(exp76_t2);
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_CREATE_T2 rc=%d\n", rc);
        kthread_stop(exp76_t1);
        return rc;
    }

    done_t1 = wait_for_completion_timeout(&exp76_t1_done,
                                          msecs_to_jiffies(EXP76_WORKER_MS));
    done_t2 = wait_for_completion_timeout(&exp76_t2_done,
                                          msecs_to_jiffies(EXP76_WORKER_MS));

    if (!done_t1)
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_T1_WORKER_TIMEOUT\n");
    if (!done_t2)
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_T2_WORKER_TIMEOUT\n");

    /*
     * kthread_stop joins both tasks. The QEMU host must impose an external
     * timeout if a broken kernel deadlocks inside spin_lock().
     */
    kthread_stop(exp76_t2);
    kthread_stop(exp76_t1);

    if (!done_t1 || !done_t2)
        return -ETIMEDOUT;

    if (READ_ONCE(exp76_t1_rc) || READ_ONCE(exp76_t2_rc))
        return -EINVAL;

    pr_info("EXP76_RT_SPIN_SLEEP PASS elapsed_us=%lld wait_us=%lld preemptible=1 irq_enabled=1\n",
            (long long)exp76_t1_sleep_us,
            (long long)exp76_t2_wait_us);
    return 0;
#endif
}

static void __exit exp76_spin_sleep_exit(void)
{
    pr_info("EXP76_RT_SPIN_SLEEP EXIT\n");
}

module_init(exp76_spin_sleep_init);
module_exit(exp76_spin_sleep_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("EXP76");
MODULE_DESCRIPTION("QEMU PREEMPT_RT spinlock schedulability and serialization probe (NOFLASH)");
