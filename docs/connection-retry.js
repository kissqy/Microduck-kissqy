/** One initial attempt, three retries, no replay of inputs. */
export class ConnectionRetry {
  constructor(clock=()=>Date.now()){this.clock=clock;this.failures=0;this.until=0;this.since=null;}
  get exhausted(){return this.failures>=4;}
  get ready(){return !this.exhausted&&this.clock()>=this.until;}
  connected(){if(this.since===null)this.since=this.clock();}
  failed(){
    const now=this.clock();if(this.since!==null&&now-this.since>=30000)this.failures=0;
    this.since=null;this.failures++;this.until=now+10000;
    return this.exhausted?'自动重试 3 次仍失败，已停止；请点击顶部重连':`10 秒后自动重试（${this.failures}/3）`;
  }
}
