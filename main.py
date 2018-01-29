#Author: AbrahamJP
#Date: 29th Jan 2018
#Version: 0.1 Beta

import sys
import subprocess
import json
import urllib2
import os
import datetime
import argparse
import time

# ----------------------------------------------------------------------------------------------------------------------

directoryName = "output"
directoryPath = ""
projectName = None
reportName = "report{}.json"
datetimeFormatString = "_%d_%m_%Y__%H_%M_%S"
verboseMode = False

# ----------------------------------------------------------------------------------------------------------------------
def getProjectArn(projectname, dataset):
    result = []

    if projectname:
        print "Retrieving project ARN"
        cmd = "aws devicefarm list-projects  --region us-west-2 --query \"projects[?name=='{}']\"".format(projectname)

        if verboseMode:
            print cmd

        response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
        jsondata = json.loads(response)

        if len(jsondata) == 1:
            result.append(jsondata[0]["arn"])
            # Update dataset
            dataset["project"] = {"name": projectname, "arn": jsondata[0]["arn"], "data": jsondata[0], "runs": {}}
        else:
            print "Unable to find DeviceFarm project with the name {}".format(projectname)

    return result


# ----------------------------------------------------------------------------------------------------------------------
def getRunArns(projectArn, dataset):
    result = []
    runs = {}

    if projectArn and len(projectArn) > 0:
        print "Retrieving runs arns"
        cmd = "aws devicefarm list-runs  --arn \"{}\" --region us-west-2".format(projectArn[0])

        if verboseMode:
            print cmd

        response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
        jsondata = json.loads(response)

        if "runs" in jsondata and len(jsondata["runs"]) > 0:
            for runs in jsondata["runs"]:
                dataset["project"]["runs"][runs["arn"]] = {"name": runs["name"], "created": runs["created"],
                                                           "data": runs, "jobs": {}}
                result.append(runs["arn"])

    if verboseMode:
        if len(result) > 0:
            print "retrieved {} run arns".format(len(result))
        else:
            print "no run arns found".format(len(result))

    return result


# ----------------------------------------------------------------------------------------------------------------------
# Jobs are devices where the tests execute
def getJobArns(runArns, dataset):
    result = []
    if runArns and len(runArns) > 0:
        print "Retrieving job arns"
        for runArn in runArns:
            cmd = "aws devicefarm list-jobs --region us-west-2  --arn \"{}\"".format(runArn)

            if verboseMode:
                print cmd

            response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
            jsondata = json.loads(response)
            if "jobs" in jsondata and len(jsondata["jobs"]) > 0:
                for job in jsondata["jobs"]:
                    dataset["project"]["runs"][runArn]["jobs"][job["arn"]] = \
                        {"name": job["name"], "data": job, "suites": {}}
                    result.append(job["arn"])

    if verboseMode:
        if len(result) > 0:
            print "retrieved {} job arns".format(len(result))
        else:
            print "no job arns found".format(len(result))

    return result


# ----------------------------------------------------------------------------------------------------------------------
def getSuitesArns(jobArns, dataset):
    result = []
    if jobArns and len(jobArns) > 0:
        print "Retrieving suite arns"
        for jobArn in jobArns:
            runArn = getRunArnFromJobArn(jobArn)

            if runArn:
                cmd = "aws devicefarm list-suites --region us-west-2  --arn \"{}\"".format(jobArn)

                if verboseMode:
                    print cmd

                response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
                jsondata = json.loads(response)

                if "suites" in jsondata and len(jsondata["suites"]) > 0:
                    for suite in jsondata["suites"]:
                        dataset["project"]["runs"][runArn]["jobs"][jobArn]["suites"][suite["arn"]] = \
                            {
                                "name": suite["name"],
                                "data": suite,
                                "tests": {}
                            }
                        result.append(suite["arn"])

    if verboseMode:
        if len(result) > 0:
            print "retrieved {} suite arns".format(len(result))
        else:
            print "no suite arns found".format(len(result))

    return result


# ----------------------------------------------------------------------------------------------------------------------
def trimArn(arnVal, arnOldName, arnNewName, trimVal):
    result = None

    if arnVal and arnOldName in arnVal:
        tokens = arnVal.split(":")

        # Update token "job" to "run"
        jobStringIndx = tokens.index(arnOldName)
        if jobStringIndx > 0:
            tokens[jobStringIndx] = arnNewName

        # Remove "00001" from the last element in the array
        guid_vals = tokens[-1].split("/")
        tokens[-1] = "/".join(guid_vals[:trimVal])

        # merge elements to a single string with the same delimiter used for splitting
        result = ":".join(tokens)

    return result


# ----------------------------------------------------------------------------------------------------------------------
def getRunArnFromJobArn(jobArn):
    return trimArn(jobArn, "job", "run", -1)


# ----------------------------------------------------------------------------------------------------------------------
def getRunArnFromSuiteArn(suiteArn):
    return trimArn(suiteArn, "suite", "run", -2)


# ----------------------------------------------------------------------------------------------------------------------
def getJobArnFromSuiteArn(suiteArn):
    return trimArn(suiteArn, "suite", "job", -1)


# ----------------------------------------------------------------------------------------------------------------------
def getRunArnFromTestArn(testArn):
    # input  arn:aws:devicefarm:us-west-2:636641907797:test:d55107d9-a254-49f5-9838-139051191831/37042d34-5380-424b-839a-8fed3cfb71b1/00000/00000/00000

    # output arn:aws:devicefarm:us-west-2:636641907797:test:d55107d9-a254-49f5-9838-139051191831/37042d34-5380-424b-839a-8fed3cfb71b1
    return trimArn(testArn, "test", "run", -3)


# ----------------------------------------------------------------------------------------------------------------------
def getJobArnFromTestArn(testArn):
    # input   arn:aws:devicefarm:us-west-2:636641907797:test:d55107d9-a254-49f5-9838-139051191831/37042d34-5380-424b-839a-8fed3cfb71b1/00000/00000/00000
    # output arn:aws:devicefarm:us-west-2:636641907797:test:d55107d9-a254-49f5-9838-139051191831/37042d34-5380-424b-839a-8fed3cfb71b1/00000
    return trimArn(testArn, "test", "job", -2)


# ----------------------------------------------------------------------------------------------------------------------
def getSuiteArnFromTestArn(testArn):
    # input   arn:aws:devicefarm:us-west-2:636641907797:test:d55107d9-a254-49f5-9838-139051191831/37042d34-5380-424b-839a-8fed3cfb71b1/00000/00000/00000
    # output arn:aws:devicefarm:us-west-2:636641907797:test:d55107d9-a254-49f5-9838-139051191831/37042d34-5380-424b-839a-8fed3cfb71b1/00000/00000
    return trimArn(testArn, "test", "suite", -1)


# ----------------------------------------------------------------------------------------------------------------------
def getTestArns(suiteArns, dataset):
    result = []
    if suiteArns and len(suiteArns) > 0:
        print "Retrieving test arns"
        for suiteArn in suiteArns:
            runArn = getRunArnFromSuiteArn(suiteArn)
            jobArn = getJobArnFromSuiteArn(suiteArn)

            if runArn and jobArn:
                cmd = "aws devicefarm list-tests --region us-west-2  --arn \"{}\"".format(suiteArn)

                if verboseMode:
                    print cmd

                response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
                jsondata = json.loads(response)

                if "tests" in jsondata and len(jsondata["tests"]) > 0:
                    for test in jsondata["tests"]:
                        dataset["project"]["runs"][runArn]["jobs"][jobArn]["suites"][suiteArn]["tests"][test["arn"]] = \
                            {
                                "name": test["name"],
                                "data": test,
                                "artifacts": {}
                            }

                        result.append(test["arn"])

    if verboseMode:
        if len(result) > 0:
            print "retrieved {} test arns".format(len(result))
        else:
            print "no test arns found".format(len(result))

    return result


# ----------------------------------------------------------------------------------------------------------------------
def getArtifacts(testArns, dataset):
    result = {}

    if testArns and len(testArns) > 0:
        for testArn in testArns:
            runArn = getRunArnFromTestArn(testArn)
            jobArn = getJobArnFromTestArn(testArn)
            suiteArn = getSuiteArnFromTestArn(testArn)

            ref = dataset["project"]["runs"][runArn]["jobs"][jobArn]["suites"][suiteArn]["tests"][testArn]

            logFileRef = getArtificatesForTestArn(testArn, "LOG")
            fileRef = getArtificatesForTestArn(testArn, "FILE")
            scrShotRef = getArtificatesForTestArn(testArn, "SCREENSHOT")

            ref["artifacts"]["LOG"] = logFileRef
            ref["artifacts"]["LOG"] = fileRef
            ref["artifacts"]["LOG"] = scrShotRef

            result = {}
            result["log"] = logFileRef
            result["file"] = fileRef
            result["screenshot"] = scrShotRef

    return result


# ----------------------------------------------------------------------------------------------------------------------
def createoutputDir(dataset):

    if verboseMode:
        print "Creating output directory"

    directoryPath = os.path.dirname(os.path.abspath(__file__))
    dirPath = os.path.join(directoryPath, directoryName)

    if verboseMode:
        print "Check directory {} exists".format(dirPath)

    if not os.path.exists(dirPath):
        if verboseMode:
            print "directory doesn't exist, hence creating directory {}".format(dirPath)

        os.makedirs(dirPath)

    if dataset:
        dataset["outputdir"] = dirPath


# ----------------------------------------------------------------------------------------------------------------------
def getArtificatesForTestArn(testArn, artifactType):
    result = []
    if testArn and len(testArn) > 0 and \
            artifactType and \
            (artifactType.upper() == "LOG" or
             artifactType.upper() == "FILE" or
             artifactType.upper() == "SCREENSHOT"):
        print "Retrieving {} artificats".format(artifactType)
        cmd = "aws devicefarm list-artifacts --region us-west-2  --arn \"{}\" --type {}".format(testArn, artifactType)

        if verboseMode:
            print cmd

        response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
        jsondata = json.loads(response)
        if "artifacts" in jsondata and len(jsondata["artifacts"]) > 0:
            for artifcat in jsondata["artifacts"]:
                result.append(downloadArtifact(artifcat))

    if verboseMode:
        if len(result) > 0:
            print "retrieved {} test arns".format(len(result))
        else:
            print "no test arns found".format(len(result))

    return result


# ----------------------------------------------------------------------------------------------------------------------
def downloadArtifact(artifact):
    result = None
    if artifact and "url" in artifact:
        print "Download artifact {}".format(artifact["url"])
        response = urllib2.urlopen(artifact["url"])
        data = response.read()

        savefilename = artifact["name"] + "." + artifact["extension"]
        filehandle = open(savefilename, "w")
        filehandle.write(data)
        filehandle.close()

    return result


# ----------------------------------------------------------------------------------------------------------------------
def getLastRunArn(runArns, dataset):

    result = []

    if runArns and len(runArns) > 0 and lastRun:
        result.append(runArns[0])

        if verboseMode:
            print "Lastrun arn: {}".format(runArns[0])

    return result


# ----------------------------------------------------------------------------------------------------------------------
def generateReport(dataset):
    result = {}
    print "Generating Report"

    if dataset:
        result["name"] = dataset["project"]["name"]
        result["tests"] = {}
        counter = 1

        for test in dataset["project"]["runs"]:
            strTestName = str(counter) + "_" + str(dataset["project"]["runs"][test]["name"])
            timeStampVal = dataset["project"]["runs"][test]["created"]
            result["tests"][strTestName] = {
                "created": str(datetime.datetime.fromtimestamp(timeStampVal).strftime('%c')),
                "details": dataset["project"]["runs"][test]["data"]
            }
            result["tests"][strTestName]["devices"] = {}

            # Devices
            for job in dataset["project"]["runs"][test]["jobs"]:
                deviceName = dataset["project"]["runs"][test]["jobs"][job]["name"]
                details = dataset["project"]["runs"][test]["jobs"][job]["data"]
                result["tests"][strTestName]["devices"][deviceName] = {
                    "tests": {},
                    "details": details
                }

                # Tests
                for suite in dataset["project"]["runs"][test]["jobs"][job]["suites"]:
                    testName = dataset["project"]["runs"][test]["jobs"][job]["suites"][suite]["name"]
                    data = dataset["project"]["runs"][test]["jobs"][job]["suites"][suite]["data"]
                    result["tests"][strTestName]["devices"][deviceName]["tests"][testName] = {"details": data}

            counter = counter + 1
    else:
        print "Dataset null, skipping report creation"

    return result


# ----------------------------------------------------------------------------------------------------------------------
def saveReport(dataset):
    global directoryPath

    dataFilename = reportName.format(time.strftime(datetimeFormatString))

    if dataset:
        if not directoryPath:
            directoryPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), directoryName)

        absoulteFilePath = os.path.join(directoryPath, dataFilename)

        filehandle = open(absoulteFilePath, "w")
        filehandle.write(json.dumps(dataset))
        filehandle.close()

        print "report saved to " + absoulteFilePath

# ----------------------------------------------------------------------------------------------------------------------
def parseArguments():

    global lastRun
    global directoryPath
    global projectName
    global verboseMode

    usageDoc = "\nGenerates report for every tests in the project \n" + \
               "\tpython main.py ReplaceWithProjectName\n" + \
               "\n\nGenerates report for only the recent test in the project \n" + \
               "\tpython main.py ReplaceWithProjectName -lastrun\n" + \
                "\n\nGenerates report for only the recent test in the project to the specific directory\n" + \
                "\tpython main.py ReplaceWithProjectName -lastrun --outputdirectory \"path\" \n"

    parser = argparse.ArgumentParser(usage=usageDoc)

    
    parser.add_argument("projectname",
                        help="DeviceFarm project name")
    parser.add_argument("-lr", "--lastrun", action='store_true',
                        help="only generated report for lastrun arn")
    parser.add_argument("-od", "--outputdirectory",
                        help="The location where the test results are to be stored")
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Enabling verbose mode, outputs statements useful for debugging\\reporting issues.")

    args = parser.parse_args()

    lastRun = args.lastrun
    directoryPath = args.outputdirectory
    projectName = args.projectname
    verboseMode = args.verbose

    if verboseMode:
        print "projectname:{} \nlastRun: {} \ndirectoryPath:{} \nVerboseMode: {}".format(
            projectName,
            lastRun,
            directoryPath,
            verboseMode)


# ----------------------------------------------------------------------------------------------------------------------
def getAllProjects():
    result = []

    cmd = "aws devicefarm list-projects --region us-west-2"
    response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
    jsondata = json.loads(response)

    for project in jsondata["projects"]:
        result.append(project["name"])

    return result

# ----------------------------------------------------------------------------------------------------------------------
def projectNameIsValid(projects, projectName):
    result = False

    try:
        idx = projects.index(projectName)
        if idx>=0:
            result = True
    except ValueError:
        result = False

    return result

# ----------------------------------------------------------------------------------------------------------------------
def validateArgs():

    result = False

    #Validate project name passed in as parameter
    projects = getAllProjects()
    result = projectNameIsValid(projects, projectName)

    if not result:
        print "Project name '{}' does not exist".format(projectName)
        print "\n\nList of DeviceFarm projects in current AWS Account\n"
        for prjName in projects:
            print prjName

    # Validate outout directory passed in as parameter
    if result and directoryPath:
        result = os.path.exists(directoryPath)
        if not result:
            print "Invalid directory path {}\n".format(directoryPath)

    return result

# ----------------------------------------------------------------------------------------------------------------------
def main():
    dataset = {}

    parseArguments()

    if validateArgs():
        print "Exporting logs for project: {}".format(projectName)

        createoutputDir(dataset)
        prjArn = getProjectArn(projectName, dataset)
        runaArns = getRunArns(prjArn, dataset)

        #Retrieve only the last run arn
        if lastRun:
            runaArns = getLastRunArn(runaArns, dataset)

        jobArns = getJobArns(runaArns, dataset)
        sutieArns = getSuitesArns(jobArns, dataset)
        testArns = getTestArns(sutieArns, dataset)
        # fileRef = getArtifacts(testArns, dataset)
        result = generateReport(dataset)
        saveReport(result)

# **********************************************************************************************************************

main()

# **********************************************************************************************************************




