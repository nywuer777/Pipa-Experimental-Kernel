// C / Linux 4.19 ARM64 PREEMPT_RT QEMU guest / verify schedulability while spinlock_t held / NO FLASH
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/interrupt.h>
#include <linux/kernel.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/preempt.h>
#include <linux/spinlock.h>

static DEFINE_SPINLOCK(exp76_lock);

static int __init exp76_spin_sleep_init(void)
{
#ifndef CONFIG_PREEMPT_RT_FULL
    pr_err("EXP76_RT_SPIN_SLEEP BLOCKED_CONFIG PREEMPT_RT_FULL=n\n");
    return -EOPNOTSUPP;
#else
    ktime_t start;
    s64 elapsed_us;

    pr_info("EXP76_RT_SPIN_SLEEP BEGIN\n");
    spin_lock(&exp76_lock);
    if (!preemptible() || irqs_disabled()) {
        spin_unlock(&exp76_lock);
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_PREEMPTION_DISABLED\n");
        return -EINVAL;
    }

    might_sleep();
    start = ktime_get();
    msleep(40);
    elapsed_us = ktime_to_us(ktime_sub(ktime_get(), start));
    spin_unlock(&exp76_lock);

    if (elapsed_us < 30000) {
        pr_err("EXP76_RT_SPIN_SLEEP FAIL_SLEEP_DURATION elapsed_us=%lld\n",
               (long long)elapsed_us);
        return -EIO;
    }
    pr_info("EXP76_RT_SPIN_SLEEP PASS elapsed_us=%lld preemptible=1 irq_enabled=1\n",
            (long long)elapsed_us);
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
MODULE_DESCRIPTION("Non-destructive PREEMPT_RT sleeping spinlock_t probe for QEMU");
