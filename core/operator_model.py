"""Allow main-thread native control while a local model is still thinking."""
import threading

def interruptible_decision(call,control,live,meta,rgb,should_stop=lambda:False):
    result={}
    ready=threading.Event()
    def worker():
        try:result["value"]=call()
        except Exception as exc:result["error"]=exc
        finally:ready.set()
    threading.Thread(target=worker,daemon=True,name="local-model-inference").start()
    stale=False
    while not ready.wait(.25):
        if should_stop():return None,live,meta,rgb,True,True
        live,meta,rgb,changed=control.drain(live,meta,rgb)
        stale|=changed
    live,meta,rgb,changed=control.drain(live,meta,rgb)
    stale|=changed
    if should_stop():return None,live,meta,rgb,True,True
    if stale or control.paused or control.review:
        return None,live,meta,rgb,True,False
    if "error" in result:raise result["error"]
    return result["value"],live,meta,rgb,False,False
