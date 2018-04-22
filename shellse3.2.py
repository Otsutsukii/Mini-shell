

import os,sys,signal
import lexer as ssp
import re
import signal
from collections import namedtuple

mode = namedtuple("mode",["redir","append"])

class processus(object):      # la class pour chaque fils qui executera la commande
    
    def __init__(self,number=None,pid=None,state=None,name=None,pipes=None):
        self.id=number
        self.pid = pid 
        self.state = state 
        self.name = name 
        self.pipes = pipes
    
    def changeState(self,newstate):
        self.state = newstate

    def changeId(self,number):
        self.id = number

    def __str__(self):
        return "[{}] pid({}) name({}) state({})".format(self.id,self.name,self.name,self.state)



class Jobs(object):     # class job control , une liste qui maintient les pipes , les job en fg et bg , en suspensions 
    
    def __init__(self, jobs=[]):
        self.jobs = jobs
    
    def addJobs(self,processus):
        self.jobs.append(processus)
    
    def searchProcessus(self,id):
        for job in self.jobs:
            if id == job.id:
                return job
        return False
    
    def searchPid(self,pid):
        for id in self.jobs:
            if pid == id.pid:
                return id
        return False
    
    def removeJob(self,id):
        temp = [job for job in self.jobs if job.id != id]
        self.jobs = temp
    
    def removebyPId(self,pid):
        temp = [job for job in self.jobs if job.pid != pid]
        self.jobs = temp
    
        
    def searchRunningPID(self):
        temp = [job.pid for job in self.jobs if job.state == "Foreground"]
        return temp[0]
    

    def getJobs(self):
        temp = [job for job in self.jobs if job.state == "Foreground"]
        return temp

    def setJobID(self):
        for i in range(len(self.jobs)):
            self.jobs[i].changeId(i+1)
        
    
    def deleteZombies(self):
        temp = [job for job in self.jobs if job.state != "Done"]
        self.jobs = temp

    def returnIndexJob(self,pid):
        for i in range(len(self.jobs)):
            if self.jobs[i].pid == pid:
                return i
        return False


class Shell(object):

    def __init__(self,pid = None,jobs= None,leaderCurrent=None):
        if pid is None:
            pid = os.getpid()
            os.setpgid(os.getpid(),os.getpid())
            os.tcsetpgrp(1,os.getpid())
        self.pere = pid
        if jobs is None:
            jobs = Jobs()
        self.jobs = jobs
        self.leaderCurrent = leaderCurrent

    def exec1(self,arguments):
        pid = os.fork()
        if pid == 0:
            os.setpgid(0,0)
            os.tcsetpgrp (1, os.getpid())
            signal.signal(signal.SIGTSTP,signal.SIG_DFL)
            self.redirect(arguments[0])
        os.setpgid(pid,pid)
        os.tcsetpgrp(0,pid)
        self.jobs.addJobs(processus(pid = pid , state = 'Foreground', name = " ".join(arguments[0][1])))
        self.jobs.setJobID()
        pid,status = os.waitpid(pid,os.WUNTRACED)
        if os.WIFSTOPPED(status):
            temp = [job for job in self.jobs.jobs if job.state == "Foreground"]
            if temp != []:
                temp[0].changeState("Suspended")
                print("Stoped by ctrl z")
        elif os.WTERMSIG(status):
            self.jobs.removebyPId(pid)
            print("Process killed")
        else:
            self.jobs.removebyPId(pid)
            print("Exited normally")      
        os.tcsetpgrp(1,self.pere)

    def runCommand(self,arguments):
        pipelines = [os.pipe() for i in range(len(arguments))]

        for i in range(len(arguments)):
            pid = os.fork()
            if pid == 0 and i == 0:
                os.setpgid(0,0)
                os.tcsetpgrp (1, os.getpid())
                os.dup2(pipelines[i][1],1)
                self.closepipes(pipelines,i)
                os.close(pipelines[i][0])
                self.redirect(arguments[i])
            
            elif pid != 0 and i == 0 :               
                os.setpgid(pid,pid)
                self.jobs.addJobs(processus(pid = pid , state = 'Foreground', name = " ".join(arguments[0][1])))
                self.jobs.setJobID() 
                self.leaderCurrent = pid
            
            elif pid != 0 :
                pid_leader = self.leaderCurrent
                job_num = self.jobs.searchPid(pid_leader)
                if job_num.pipes is None:
                    job_num.pipes = [pid]
                else:
                    job_num.pipes.append(pid)
                indice = self.jobs.returnIndexJob(pid)
                self.jobs.jobs[indice] = job_num
                
            elif pid == 0 and i != 0 and i != len(arguments)-1:
                os.setpgid(0,self.leaderCurrent)
                os.dup2(pipelines[i][1],1)
                os.dup2(pipelines[i-1][0],0)
                self.closepipes(pipelines,i)
                os.close(pipelines[i][1])
                os.close(pipelines[i][0])
                self.redirect(arguments[i])

            elif pid == 0 and i == len(arguments)-1:
                os.setpgid(0,self.leaderCurrent)
                os.dup2(pipelines[i-1][0],0)
                self.closepipes(pipelines,i)
                os.close(pipelines[i][0])
                os.close(pipelines[i][1])
                #os.execvp(arguments[i][0],arguments[i][1])
                self.redirect(arguments[i])

        self.closepipes(pipelines,-1)
        for i in range(len(arguments)):
            pid,status = os.waitpid(-1,os.WUNTRACED)
            if os.WIFSTOPPED(status):
                temp = [job for job in self.jobs.jobs if job.state == "Foreground"] 
                if temp != []: 
                    temp[0].changeState("Suspended")
                    print("Stoped by ctrl z")
            elif os.WTERMSIG(status):
                self.jobs.removebyPId(pid)
                print("Process killed")
            else:
                self.jobs.removebyPId(pid)
                print("exited normally")      
        #os.wait()
        os.tcsetpgrp(1,self.pere)
        return       


    def listen(self):
        isRunning = True
        signal.signal(signal.SIGTTIN,signal.SIG_IGN)
        signal.signal(signal.SIGTTOU,signal.SIG_IGN)
        signal.signal(signal.SIGTSTP,self.handler_ctrl_z)
        signal.signal(signal.SIGTERM,self.handler_ctrl_c)
        while(isRunning):
            arguments = input(">>")
            if re.match(r"exit",arguments):
                isRunning = False
                break
            elif re.match(r"bg %[1-9]+",arguments):
                job_id = list(map(int,re.findall(r"[1-9]+",arguments)))
                self.bg(job_id)

            elif re.match(r"fg %[1-9]+",arguments) or re.match(r"fg",arguments):
                job_id = list(map(int,re.findall(r"[1-9]+",arguments)))
                self.fg(job_id) 
            
            elif re.match(r"jobs",arguments):
                job_id = list(map(int,re.findall(r"[1-9]+",arguments)))
                self.cmdjobs(job_id)

            elif re.match(r"kill %[1-9]+",arguments):
                job_id = list(map(int,re.findall(r"[1-9]+",arguments)))
                self.kill(job_id)
            
            elif re.match(r"%t",arguments):
                arguments = ssp.get_parser().parse(arguments[2:])
                arg = self.parse(arguments)
                print(arg)
                
            elif arguments != "":
                arg = ssp.get_parser().parse(arguments)
                #self.runCommand([["ps","auxwww"],["grep","fred"],["more"]])
                arg2 = self.parse(arg)
                if len(arg2) == 1:
                    self.exec1(arg2)
                else:
                    self.runCommand(arg2)
                #self.runCommand([["ps",["ps","auxwww"]],["grep",["grep","fred"]],["more",["more"]]])
                #self.OneCommand([["ls",["ls","-al"],[False,True,False]]])
        return
     
    
    def wait2(self,sig,ignore):
        os.wait()
        return 
    
    def closepipes(self,pipelist,index):
        for i in range(len(pipelist)):
            if index != i :
                os.close(pipelist[i][0])
                os.close(pipelist[i][1])
        return pipelist[index]      


    def parse(self,args):
        commandes=[]
        for p in args:
            temp = []
            temp.append(p._cmd.getCommand())
            temp.append([p._cmd.getCommand()]+p._cmd.getArgs())
            R ={0:0}
            for redir in p._redirs._redirs:
                if redir.__class__.__name__=="ERRREDIR":
                    R["ERR"]=mode(redir.getFileSpec(),redir._append)
                elif redir.__class__.__name__=="OUTREDIR":
                    R["OUT"]=mode(redir.getFileSpec(),redir._append)
                elif isinstance(redir,ssp.INREDIR):
                    R["IN"]=redir.getFileSpec()
            temp.append(R)
            commandes.append(temp)
        return commandes       
    
    def waitChild(self,sig,ignore):
        pid = 1
        while pid>0:
            try :
                pid , status = os.waitpid(-1,os.WNOHANG)
                if os.WIFEXITED(status):
                    print("child %d terminated normally with exit status=%d",pid,os.WEXITSTATUS())
            except OSError:
                pass
        return 
            
        

    
    def redirect(self,argument):
        with open("file", "wb") as f:
            f.write("{} {}".format(argument, type(argument)).encode("utf-8"))
    
        if 'In' in argument[2]:
            dic = argument[2]
            fd = os.open(dic['In'].redir,os.O_RDONLY)
            os.dup2(fd,0)
            os.close(fd)
            
        if 'OUT' in argument[2]:
            if argument[2]['OUT'].append == True:
                fd2 = os.open(argument[2]['OUT'].redir,os.O_WRONLY|os.O_CREAT|os.O_APPEND,777)
                os.dup2(fd2,1)
                os.close(fd2)
            else:
                fd2 = os.open(argument[2]['OUT'].redir,os.O_WRONLY|os.O_CREAT,777)
                os.dup2(fd2,1)
                os.close(fd2)

        if 'ERR' in argument[2]:
            if argument[2]['ERR'].append == True:
                fd2 = os.open(argument[2]['ERR'].redir,os.O_WRONLY|os.O_CREAT|os.O_APPEND,777)
                os.dup2(fd2,2)
                os.close(fd2)
            else:
                fd2 = os.open(argument[2]['ERR'].redir,os.O_WRONLY|os.O_CREAT,777)
                os.dup2(fd2,2)
                os.close(fd2)
        
        os.execvp(argument[0],argument[1])
    
    
    def fg(self,numero_job):
        if numero_job == []:
            fils = [job.pid for job in self.jobs.jobs]
            pidfils = fils[-1]
            pgid = os.getpgid(pidfils)
            os.tcsetpgrp(1,pgid)
            fgpid = pgid
            os.kill(-pgid,signal.SIGCONT)
            pid , status = os.waitpid(pidfils,os.WUNTRACED)
            if os.WIFSTOPPED(status):
                    print("Fg stopped")
            elif os.WTERMSIG(status):
                self.jobs.removebyPId(pid)
                print("Fg Process killed")
            else:
                self.jobs.removebyPId(pidfils)
            os.tcsetpgrp(1,self.pere)
        else:
            fils = [job.pid for job in self.jobs.jobs]
            pidfils = fils[numero_job[0] - 1]
            pgid = os.getpgid(pidfils)
            os.tcsetpgrp(1,pgid)
            fgpid = pgid
            os.kill(-pgid,signal.SIGCONT)
            pid , status = os.waitpid(pidfils,os.WUNTRACED)
            if os.WIFSTOPPED(status):
                    print("Fg stopped")
            elif os.WTERMSIG(status):
                self.jobs.removebyPId(pid)
                print("Fg Process killed")
            else:
                self.jobs.removebyPId(pidfils)
            os.tcsetpgrp(1,self.pere)

    def bg(self,numero_job):
        if numero_job == []:
            fils = [job for job in self.jobs.jobs]
            pidfils = fils[-1].pid
            pgid = os.getpgid(pidfils)
            fgpid = pgid
            self.jobs.jobs[-1].changeState("Running")
            os.kill(-pgid,signal.SIGCONT)
        else:
            fils = [job for job in self.jobs.jobs]
            self.jobs.jobs[numero_job[0]-1].changeState("Running")
            pgid = os.getpgid(pidfils)
            fgpid = pgid
            os.kill(-pgid,signal.SIGCONT)


    def kill(self,numero_job):
        if numero_job == []:
            pass
        else:    
            fils = [job.pid for job in self.jobs.jobs]
            os.kill(fils[numero_job[0]-1],signal.SIGKILL)
            self.fg(numero_job)

    def cmdjobs(self,numero_job):
        if numero_job == []:
            for job in self.jobs.jobs:
                if(job.pipes):
                    print([job.id], "\t", job.pid, "\t", job.name ,"\t", job.state, "\t" , job.pipes)
                else:
                    print([job.id], "\t", job.pid, "\t", job.name ,"\t", job.state)
        else:
            job = self.jobs.jobs[numero_job[0]-1]
            if(job.pipes):
                print([job.id], "\t", job.pid, "\t", job.name ,"\t", job.state, "\t" , job.pipes)
            else:
                print([job.id], "\t", job.pid, "\t", job.name ,"\t", job.state)

    def handler_ctrl_z(self,signale,ignore):
        fils = self.jobs
        if os.getpid() == self.pere:
            os.kill(fils.searchRunningPID(),signal.SIGTSTP)
            cmd.listen()
        elif os.getpid() == fils.searchRunningPID():
            signal.pause()

    def handler_ctrl_c(self,signale,ign):
        fils = self.jobs
        if fils != []:
            if os.getpid() == self.pere:
                os.kill(fils.searchRunningPID(),signal.SIGKILL)
                cmd.listen()



if __name__=="__main__":
    cmd = Shell()
    #result = ssp.get_parser().parse('foo toto > bar 2>> baz | fizz >> fuzzz << EOF | goo > gooo < gaa 2> ga | dummy')
    #print("\n")
    #print("commands examples \n")
    #for p in result:
    #    print("p._cmd._command: ",p._cmd._command)
    #    print("p._cmd._args: ",p._cmd._args)
    #    print("p._cmd._args: ",p._redirs._redirs)
    #    for redir in p._redirs._redirs:
    #        print(redir.getFileSpec())
    jobs = Jobs()
    cmd.listen()
    #print(cmd.peregp)
