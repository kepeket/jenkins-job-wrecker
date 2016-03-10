import logging
import re
import pprint
from collections import OrderedDict

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

from copy import deepcopy
def dict_merge(a, b):
    if not isinstance(b, dict):
        return b
    result = OrderedDict(deepcopy(a))
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result

# Handle "<actions/>"
def handle_actions(top):
    # Nothing to do if it's empty.
    # Otherwise...
    if list(top) and len(list(top)) > 0:
        raise NotImplementedError("Don't know how to handle a "
                                  "non-empty <actions> element.")


# Handle "<description>my cool job</description>"
def handle_description(top):
    return [['description', top.text]]


# Handle "<keepDependencies>false</keepDependencies>"
def handle_keepdependencies(top):
    # JJB cannot handle any other value than false, here.
    # There is no corresponding YAML option.
    return None


# Handle "<properties>..."
def handle_properties(top):
    properties = []
    parameters = []
    result = [['properties', properties], ['parameters', parameters]]
    for child in top:
        try:
            # GitHub
            if child.tag == 'com.coravy.hudson.plugins.github.GithubProjectProperty':   # NOQA
                github = handle_github_project_property(child)
                properties.append(github)

            # Parameters
            elif child.tag == 'hudson.model.ParametersDefinitionProperty':
                parametersdefs = handle_parameters_property(child)
                for pd in parametersdefs:
                    parameters.append(pd)
            elif child.tag == 'com.sonyericsson.rebuild.RebuildSettings':
                rebuild = handle_rebuild_settings_property(child)
                properties.append(rebuild)
            elif child.tag == 'hudson.plugins.copyartifact.CopyArtifactPermissionProperty':
                copy_artifact = handle_copy_artifact_property(child)
                properties.append(copy_artifact)
                    
            elif child.tag == 'jenkins.plugins.slack.SlackNotifier_-SlackJobProperty':
                slack = OrderedDict()

                known_slack_properties = {
                    'startNotification': 'notify-start',
                    'notifySuccess': 'notify-success',
                    'notifyAborted': 'notify-aborted',
                    'notifyNotBuilt': 'notify-not-built',
                    'notifyUnstable': 'notify-unstable',
                    'notifyFailure': 'notify-failure',
                    'notifyRepeatedFailure': 'notify-repeated-failure',
                    'notifyBackToNormal': 'notify-back-to-normal',
                    'includeTestSummary': 'include-test-summary',
                    'showCommitList': 'show-commit-list',
                }

                customMessageEnabled = False
                customMessage = ''

                enableSlack = False

                for slackProp in child:
                    if slackProp.tag in known_slack_properties:
                        if slackProp.text == 'true':
                            slack[known_slack_properties[slackProp.tag]] = True
                            enableSlack = True
                    elif slackProp.tag == 'includeCustomMessage':
                        customMessageEnabled = slackProp.text == 'true'
                    elif slackProp.tag == 'customMessage':
                        customMessage = slackProp.text
                    elif slackProp.tag == 'room':
                        if slackProp.text:
                            slack['room'] = slackProp.text
                    elif slackProp.tag in ['teamDomain', 'token'] and not(slackProp.text) == 0:
                        pass
                    else:
                        raise NotImplementedError("cannot handle Slack property %s" % slackProp.tag)

                if customMessageEnabled:
                    slack['custom-message'] = customMessage

                if enableSlack:
                    slack = OrderedDict([('enabled', True)] + slack.items())
                    result.append(['slack', slack])

            else:
                raise NotImplementedError("cannot handle property %s" % child.tag)

        except NotImplementedError, e:
            print "going raw because: %s" % e
            insert_rawxml(child, properties)

    return result


# Handle "<com.coravy.hudson.plugins.github.GithubProjectProperty>..."
def handle_github_project_property(top):
    github = OrderedDict()
    for child in top:
        if child.tag == 'projectUrl':
            github['url'] = child.text
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)
    return {'github': github}

# Handle "<hudson.plugins.copyartifact.CopyArtifactPermissionProperty>..."
def handle_copy_artifact_property(top):
    copy_artifact = OrderedDict()
    projects = []
    for child in top:
        if child.tag == 'projectNameList':
            for c in child:
                if c.tag == 'string':
                    projects.append(c.text)
                else:
                    raise NotImplementedError("cannot handle copy artifact project \
                    of type %s" % c.tag)
            copy_artifact['projects'] = ','.join(projects)
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)
    return {'copyartifact': copy_artifact}


# Handle "<com.sonyericsson.rebuild.RebuildSettings>..."
def handle_rebuild_settings_property(top):
    rebuild = OrderedDict()
    for child in top:
        if child.tag == 'autoRebuild':
            rebuild['auto-rebuild'] = child.text == 'true'
        elif child.tag == 'rebuildDisabled':
            rebuild['rebuild-disabled'] = child.text == 'true'
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)
    return {'rebuild': rebuild}


# Handle "<hudson.model.ParametersDefinitionProperty>..."
def handle_parameters_property(top):
    parameters = []
    for parameterdefs in top:
        if parameterdefs.tag != 'parameterDefinitions':
            raise NotImplementedError("cannot handle "
                                      "XML %s" % parameterdefs.tag)
        for parameterdef in parameterdefs:
            if parameterdef.tag == 'hudson.model.StringParameterDefinition':
                parameter_type = 'string'
            elif parameterdef.tag == 'hudson.model.BooleanParameterDefinition':
                parameter_type = 'bool'
            else:
                insert_rawxml(parameterdef, parameters)
                continue

            parameter_settings = OrderedDict()
            for defsetting in parameterdef:
                key = {
                    'defaultValue': 'default',
                }.get(defsetting.tag, defsetting.tag)
                # If the XML had a blank string, don't pass None to PyYAML,
                # because PyYAML will translate this as "null". Just use a
                # blank string to be safe.
                if defsetting.text is None:
                    value = ''
                # If the XML has a value of "true" or "false", we shouldn't
                # treat the value as a string. Use native Python booleans
                # so PyYAML will not quote the values as strings.
                elif defsetting.text == 'true':
                    value = True
                elif defsetting.text == 'false':
                    value = False
                # Assume that PyYAML will handle everything else correctly
                else:
                    value = defsetting.text
                parameter_settings[key] = value
            parameters.append({parameter_type: parameter_settings})
    return parameters


# Handle "<scm>..."
def handle_scm(top):
    if 'class' in top.attrib:
        if top.attrib['class'] == 'hudson.scm.NullSCM':
            return None

        if top.attrib['class'] == 'org.jenkinsci.plugins.multiplescms.MultiSCM':
            scms = []
            for scm in top[0]:
                scms.append(handle_scm(scm)[0][1][0])
            return [['scm', scms]]

    scm = []

    if top.tag != 'hudson.plugins.git.GitSCM' and \
            top.attrib['class'] != 'hudson.plugins.git.GitSCM':
        raise NotImplementedError("%s scm not supported" % top.attrib['class'])

    try:
        git = OrderedDict()

        for child in top:

            if child.tag == 'configVersion':
                continue    # we don't care

            elif child.tag == 'userRemoteConfigs':
                if len(list(child)) != 1:
                    # expected "hudson.plugins.git.UserRemoteConfig" tag
                    raise NotImplementedError("%s not supported with %i "
                                              "children" % (child.tag,
                                                            len(list(child))))

                for setting in child[0]:
                    if setting.tag in ['url', 'name', 'refspec']:
                        git[setting.tag] = setting.text
                    elif setting.tag == 'credentialsId':
                        git['credentials-id'] = setting.text
                    else:
                        raise NotImplementedError("cannot handle UserRemoteConfig setting %s" % setting.tag)

            elif child.tag == 'gitTool':
                git['git-tool'] = child.text

            elif child.tag == 'excludedUsers':
                if child.text:
                    users = child.text.split()
                    git['excluded-users'] = users

            elif child.tag == 'buildChooser':
                if child.attrib['class'] == \
                        'hudson.plugins.git.util.DefaultBuildChooser':
                    continue
                else:
                    # see JJB's jenkins_jobs/modules/scm.py
                    # for other build choosers
                    raise NotImplementedError("%s build "
                                              "chooser" % child.attrib['class'])

            elif child.tag == 'disableSubmodules':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    raise NotImplementedError("TODO: %s" % child.tag)

            elif child.tag == 'recursiveSubmodules':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    raise NotImplementedError("TODO: %s" % child.tag)

            elif child.tag == 'authorOrCommitter':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    git['use-author'] = True

            elif child.tag == 'useShallowClone':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    git['shallow-clone'] = True

            elif child.tag == 'ignoreNotifyCommit':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    git['ignore-notify'] = True

            elif child.tag == 'wipeOutWorkspace':
                git['wipe-workspace'] = (child.text == 'true')

            elif child.tag == 'skipTag':
                # 'false' is the JJB default. But 'true' is the Jenkins
                # default!
                if child.text != 'true':
                    git['skip-tag'] = False

            elif child.tag == 'pruneBranches':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    git['prune'] = True

            elif child.tag == 'remotePoll':
                # 'false' is the default and needs no explict YAML.
                if child.text == 'true':
                    git['fastpoll'] = True

            elif child.tag == 'relativeTargetDir':
                # If it's empty, no explicit 'basedir' YAML needed.
                if child.text:
                    git['basedir'] = child.text

            elif child.tag == 'reference':
                # If it's empty, we're good
                if child.text or len(list(child)) > 0:
                    raise NotImplementedError(child.tag)

            elif child.tag == 'gitConfigName':
                # If it's empty, we're good
                if child.text or len(list(child)) > 0:
                    raise NotImplementedError(child.tag)

            elif child.tag == 'gitConfigEmail':
                # If it's empty, we're good
                if child.text or len(list(child)) > 0:
                    raise NotImplementedError(child.tag)

            elif child.tag == 'scmName':
                # If it's empty, we're good
                if child.text or len(list(child)) > 0:
                    raise NotImplementedError(child.tag)

            elif child.tag == 'branches':
                if child[0][0].tag != 'name':
                    raise NotImplementedError("%s XML not supported"
                                              % child[0][0].tag)
                branches = []
                for item in child:
                    for branch in item:
                        branches.append(branch.text)
                git['branches'] = branches

            elif child.tag == 'localBranch':
                git['local-branch'] = child.text

            elif child.tag == 'doGenerateSubmoduleConfigurations':
                if len(list(child)) != 0:
                    raise NotImplementedError("%s not supported with %i children"
                                              % (child.tag, len(list(child))))
                # JJB doesn't handle this element anyway. Just continue on.
                continue

            elif child.tag == 'submoduleCfg':
                if len(list(child)) > 0:
                    raise NotImplementedError("%s not supported with %i children"
                                              % (child.tag, len(list(child))))

            elif child.tag == 'browser':
                if child.attrib['class'] == 'hudson.plugins.git.browser.GitBlitRepositoryBrowser':
                    git['browser'] = 'gitblit'
                    for item in child:
                        if item.tag == 'url':
                            git['browser-url'] = item.text
                        elif item.tag == 'projectName':
                            git['project-name'] = item.text
                        else:
                            raise NotImplementedError("cannot handle browser config %s", item.tag)
                elif child.attrib['class'] == 'hudson.plugins.git.browser.GithubWeb':
                    git['browser'] = 'githubweb'
                    for item in child:
                        if item.tag == 'url':
                            git['browser-url'] = item.text
                        else:
                            raise NotImplementedError("cannot handle browser config %s", item.tag)
                elif child.text or len(list(child)) > 0:
                    raise NotImplementedError("cannot handle browser %s" % child.attrib['class'])

            elif child.tag == 'extensions':
                clean = OrderedDict()
                for ext in child:
                    if ext.tag == 'hudson.plugins.git.extensions.impl.RelativeTargetDirectory':
                        git['basedir'] = ext.findtext('relativeTargetDir')

                    elif ext.tag == 'hudson.plugins.git.extensions.impl.CloneOption':
                        if ext.findtext('shallow') == 'true':
                            git['shallow-clone'] = True
                        referenceRepo = ext.findtext('reference')
                        if len(referenceRepo):
                            git['reference-repo'] = referenceRepo

                    elif ext.tag == 'hudson.plugins.git.extensions.impl.CleanBeforeCheckout':
                        clean['before'] = True

                    elif ext.tag == 'hudson.plugins.git.extensions.impl.CleanCheckout':
                        clean['after'] = True

                    elif ext.tag == 'hudson.plugins.git.extensions.impl.WipeWorkspace':
                        git['wipe-workspace'] = True

                    elif ext.tag == 'hudson.plugins.git.extensions.impl.PerBuildTag':
                        git['skip-tag'] = False

                    elif ext.tag == 'hudson.plugins.git.extensions.impl.LocalBranch':
                        git['local-branch'] = ext.findtext('localBranch')

                    else:
                        raise NotImplementedError("cannot handle Git extension %s" % ext.tag)

                if len(clean):
                    git['clean'] = clean

            else:
                raise NotImplementedError("cannot handle Git option %s" % child.tag)

        # JJB defaults wipe-workspace to true, but Jenkins defaults to false
        if 'wipe-workspace' not in git:
            git['wipe-workspace'] = False

        # JJB defaults skip-tag to false, but Jenkins defaults to true
        if 'skip-tag' not in git:
            git['skip-tag'] = True

        scm.append({'git': git})
    except NotImplementedError, e:
        print "going raw because: %s" % e
        insert_rawxml(top, scm)
    return [['scm', scm]]


# Handle "<canRoam>true</canRoam>"
def handle_canroam(top):
    # JJB doesn't have an explicit YAML setting for this; instead, it
    # infers it from the "node" parameter. So there's no need to handle the
    # XML here.
    return None


# Handle "<disabled>false</disabled>"
def handle_disabled(top):
    return [['disabled', top.text == 'true']]


# Handle "<blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>" NOQA
def handle_blockbuildwhendownstreambuilding(top):
    return [['block-downstream', top.text == 'true']]


# Handle "<blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>" NOQA
def handle_blockbuildwhenupstreambuilding(top):
    return [['block-upstream', top.text == 'true']]


def handle_triggers(top):
    triggers = []

    for child in top:
        triggers.append(handle_trigger(child))

    return [['triggers', triggers]]


def handle_trigger(trigger):
    try:
        if trigger.tag == 'hudson.triggers.SCMTrigger':
            pollscm = OrderedDict()
            for setting in trigger:
                if setting.tag == 'spec':
                    pollscm['cron'] = setting.text
                elif setting.tag == 'ignorePostCommitHooks':
                    pollscm['ignore-post-commit-hooks'] = \
                        (setting.text == 'true')
                else:
                    raise NotImplementedError("cannot handle scm trigger "
                                              "setting %s" % setting.tag)
            return {'pollscm': pollscm}

        elif trigger.tag == 'hudson.triggers.TimerTrigger':
            return {'timed': trigger.findtext('spec')}

        elif trigger.tag == 'jenkins.triggers.ReverseBuildTrigger':
            reverse = OrderedDict()
            for setting in trigger:
                if setting.tag == 'upstreamProjects':
                    reverse['jobs'] = setting.text
                elif setting.tag == 'threshold':
                    pass    # TODO
                elif setting.tag == 'spec':
                    pass    # TODO
                else:
                    raise NotImplementedError("cannot handle reverse trigger "
                                              "setting %s" % setting.tag)
            return {'reverse': reverse}

        elif trigger.tag == 'com.sonyericsson.hudson.plugins.gerrit.trigger.hudsontrigger.GerritTrigger':
            gerrit = OrderedDict()
            for setting in trigger:
                if setting.tag == 'gerritProjects':
                    projects = []
                    for projectChild in setting:
                        project = OrderedDict()
                        project['project-compare-type'] = projectChild.findtext('compareType')
                        project['project-pattern'] = projectChild.findtext('pattern')

                        branches = []
                        for branchChild in projectChild.find('branches'):
                            branch = OrderedDict()
                            branch['branch-compare-type'] = branchChild.findtext('compareType')
                            branch['branch-pattern'] = branchChild.findtext('pattern')
                            branches.append(branch)

                        project['branches'] = branches

                        projects.append(project)

                    gerrit['projects'] = projects

                elif setting.tag == 'triggerOnEvents':
                    events = []
                    for eventChild in setting:
                        event = None
                        if eventChild.tag == 'com.sonyericsson.hudson.plugins.gerrit.trigger.hudsontrigger.events.PluginRefUpdatedEvent':
                            event = 'ref-updated-event'
                        elif eventChild.tag == 'com.sonyericsson.hudson.plugins.gerrit.trigger.hudsontrigger.events.PluginDraftPublishedEvent':
                            event = 'draft-published-event'
                        elif eventChild.tag == 'com.sonyericsson.hudson.plugins.gerrit.trigger.hudsontrigger.events.PluginPatchsetCreatedEvent':
                            event = 'patchset-created-event'
                            excludes = OrderedDict()
                            for excludeChild in eventChild:
                                if excludeChild.tag == 'excludeDrafts':
                                    if excludeChild.text == 'true':
                                        excludes['exclude-drafts'] = True
                                elif excludeChild.tag == 'excludeTrivialRebase':
                                    if excludeChild.text == 'true':
                                        excludes['exclude-trivial-rebase'] = True
                                elif excludeChild.tag == 'excludeNoCodeChange':
                                    if excludeChild.text == 'true':
                                        excludes['exclude-no-code-change'] = True
                            if len(excludes) != 0:
                                event = OrderedDict([(event, excludes)])
                        else:
                            raise NotImplementedError("cannot handle Gerrit event %s" % eventChild.tag)

                        events.append(event)

                    gerrit['trigger-on'] = events

                else:
                    pass

            return {'gerrit': gerrit}

        else:
            raise NotImplementedError("cannot handle trigger %s" % trigger.tag)

    except NotImplementedError, e:
        print "going raw because: %s" % e
        return create_rawxml(trigger)


def handle_concurrentbuild(top):
    return [['concurrent', top.text == 'true']]


def handle_axes(top):
    axes = []
    for child in top:

        if child.tag == 'hudson.matrix.LabelExpAxis':
            axis = {'type': 'label-expression'}
            for axis_element in child:
                if axis_element.tag == 'name':
                    axis['name'] = axis_element.text
                if axis_element.tag == 'values':
                    values = []
                    for value_element in axis_element:
                        values.append(value_element.text)
                    axis['values'] = values
            axes.append({'axis': axis})

        elif child.tag == 'hudson.matrix.LabelAxis':
            axis = {'type': 'slave'}
            for axis_element in child:
                if axis_element.tag == 'name':
                    axis['name'] = axis_element.text
                if axis_element.tag == 'values':
                    values = []
                    for value_element in axis_element:
                        values.append(value_element.text)
                    axis['values'] = values
            axes.append({'axis': axis})

        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    return [['axes', axes]]


def handle_builders(top):
    builders = []
    for child in top:
        builders.append(handle_builder(child))
    return [['builders', builders]]


def handle_builder(builder):
    try:
        if builder.tag == 'hudson.plugins.copyartifact.CopyArtifact':
            copyartifact = OrderedDict()
            selectdict = {
                'StatusBuildSelector': 'last-successful',
                'LastCompletedBuildSelector': 'last-completed',
                'SpecificBuildSelector': 'specific-build',
                'SavedBuildSelector': 'last-saved',
                'TriggeredBuildSelector': 'upstream-build',
                'PermalinkBuildSelector': 'permalink',
                'WorkspaceSelector': 'workspace-latest',
                'ParameterizedBuildSelector': 'build-param',
                'DownstreamBuildSelector': 'downstream-build'}
            for copy_element in builder:
                if copy_element.tag == 'project':
                    copyartifact[copy_element.tag] = copy_element.text
                elif copy_element.tag == 'filter':
                    copyartifact[copy_element.tag] = copy_element.text
                elif copy_element.tag == 'target':
                    copyartifact[copy_element.tag] = copy_element.text
                elif copy_element.tag == 'excludes':
                    copyartifact['exclude-pattern'] = copy_element.text
                elif copy_element.tag == 'selector':
                    select = copy_element.attrib['class']
                    select = select.replace('hudson.plugins.copyartifact.', '')
                    which_build = selectdict[select]
                    copyartifact['which-build'] = which_build
                    if which_build == 'build-param':
                        copyartifact['param'] = copy_element.findtext('parameterName')
                elif copy_element.tag == 'flatten':
                    copyartifact[copy_element.tag] = \
                        (copy_element.text == 'true')
                elif copy_element.tag == 'doNotFingerprintArtifacts':
                    # Not yet implemented in JJB
                    if copy_element.text != "false":
                        raise NotImplementedError("cannot handle doNotFingerprintArtifacts != false")
                    continue
                elif copy_element.tag == 'optional':
                    copyartifact[copy_element.tag] = \
                        (copy_element.text == 'true')
                else:
                    raise NotImplementedError("cannot handle "
                                              "XML %s" % copy_element.tag)
            return {'copyartifact': copyartifact}

        elif builder.tag == 'hudson.tasks.Shell':
            for shell_element in builder:
                # Assumption: there's only one <command> in this
                # <hudson.tasks.Shell>
                if shell_element.tag == 'command':
                    shell = shell_element.text
                else:
                    raise NotImplementedError("cannot handle "
                                              "XML %s" % shell_element.tag)
            return {'shell': shell}

        elif builder.tag == 'org.jenkinsci.plugins.conditionalbuildstep.singlestep.SingleConditionalBuilder':
            conditional = OrderedDict()
            for item in builder:
                if item.tag == 'condition':
                    conditionClass = item.attrib['class']
                    if conditionClass == 'org.jenkins_ci.plugins.run_condition.core.ExpressionCondition':
                        conditional['condition-kind'] = 'regex-match'
                        conditional['regex'] = item.findtext('expression')
                        conditional['label'] = item.findtext('label')

                    elif conditionClass == 'org.jenkins_ci.plugins.run_condition.core.AlwaysRun':
                        conditional['condition-kind'] = 'always'

                    elif conditionClass == 'org.jenkins_ci.plugins.run_condition.core.NeverRun':
                        conditional['condition-kind'] = 'never'

                    elif conditionClass == 'org.jenkins_ci.plugins.run_condition.core.StatusCondition':
                        conditional['condition-kind'] = 'current-status'
                        conditional['condition-worst'] = item.findtext('worstResult/name')
                        conditional['condition-best'] = item.findtext('bestResult/name')

                    else:
                        raise NotImplementedError("cannot handle condition %s" % conditionClass)

                elif item.tag == 'runner':
                    runnerClass = item.attrib['class']
                    if runnerClass == 'org.jenkins_ci.plugins.run_condition.BuildStepRunner$Fail':
                        pass
                    else:
                        raise NotImplementedError("cannot handle conditional runner %s" % runnerClass)

                elif item.tag == 'buildStep':
                    # Turn the 'buildStep' into a regular builder node, in case it ends up
                    # emitted as raw XML, because JJB will put back the element name in
                    # 'class' in that case
                    builder = item.copy()
                    builder.tag = builder.attrib.pop('class')
                    conditional['steps'] = [handle_builder(builder)]

                else:
                    raise NotImplementedError("cannot handle conditional property %s" % item.tag)

            return {'conditional-step': conditional}

        elif builder.tag == 'hudson.plugins.parameterizedtrigger.TriggerBuilder':
            triggerConfigs = []
            for configNode in builder.find('configs'):
                if configNode.tag != 'hudson.plugins.parameterizedtrigger.BlockableBuildTriggerConfig':
                    raise NotImplementedError("cannot handle trigger config %s" % item.tag)

                triggerConfig = OrderedDict()
                for propertyNode in configNode:
                    if propertyNode.tag == 'projects':
                        triggerConfig['project'] = \
                            propertyNode.text.split(',') \
                            if ',' in propertyNode.text \
                            else propertyNode.text

                    elif propertyNode.tag == 'configs':
                        for confconf in propertyNode:
                            if confconf.tag == 'hudson.plugins.parameterizedtrigger.PredefinedBuildParameters':
                                triggerConfig['predefined-parameters'] = confconf.findtext('properties')
                            else:
                                raise NotImplementedError("cannot handle trigger config config %s" % confconf.tag)

                    elif propertyNode.tag == 'configFactories':
                        parameterFactories = []
                        for factoryNode in propertyNode:
                            factory = OrderedDict()
                            if factoryNode.tag == 'hudson.plugins.parameterizedtrigger.FileBuildParameterFactory':
                                factory['factory'] = 'filebuild'
                                for factoryProperty in factoryNode:
                                    if factoryProperty.tag == 'filePattern':
                                        factory['file-pattern'] = factoryProperty.text

                                    elif factoryProperty.tag == 'noFilesFoundAction':
                                        factory['no-files-found-action'] = factoryProperty.text

                                    else:
                                        raise NotImplementedError("cannot handle trigger factory property %s" % factoryProperty.tag)

                            else:
                                raise NotImplementedError("cannot handle trigger factory %s" % factoryNode.tag)

                            parameterFactories.append(factory)

                        triggerConfig['parameter-factories'] = parameterFactories

                    elif propertyNode.tag == 'block':
                        triggerConfig['block'] = True
                        blockThresholds = OrderedDict([
                            ('build-step-failure-threshold', 'never'),
                            ('unstable-threshold', 'never'),
                            ('failure-threshold', 'never'),
                        ])
                        for threshold in propertyNode:
                            value = threshold.findtext('name').lower()
                            if value not in ['never', 'success', 'unstable', 'failure']:
                                raise NotImplementedError("cannot handle threshold value %s" % value)
                            if threshold.tag == 'buildStepFailureThreshold':
                                blockThresholds['build-step-failure-threshold'] = value
                            elif threshold.tag == 'unstableThreshold':
                                blockThresholds['unstable-threshold'] = value
                            elif threshold.tag == 'failureThreshold':
                                blockThresholds['failure-threshold'] = value
                            else:
                                raise NotImplementedError("cannot handle threshold %s" % threshold.tag)
                        triggerConfig['block-thresholds'] = blockThresholds

                    elif propertyNode.tag == 'condition' and propertyNode.text == 'ALWAYS' \
                        or (propertyNode.tag in ['triggerWithNoParameters', 'buildAllNodesWithLabel']
                            and propertyNode.text == 'false'):
                        pass

                    else:
                        raise NotImplementedError("cannot handle trigger config property %s" % propertyNode.tag)

                triggerConfigs.append(triggerConfig)

            return {'trigger-builds': triggerConfigs}

        else:
            raise NotImplementedError("cannot handle builder %s" % builder.tag)

    except NotImplementedError, e:
        print "going raw because: %s" % e
        return create_rawxml(builder)


def handle_publishers(top):
    publishers = []
    for child in top:
        try:

            if child.tag == 'hudson.tasks.ArtifactArchiver':
                archive = OrderedDict()
                for element in child:
                    if element.tag == 'artifacts':
                        archive['artifacts'] = element.text
                    elif element.tag == 'allowEmptyArchive':
                        archive['allow-empty'] = (element.text == 'true')
                    elif element.tag == 'excludes':
                        archive['excludes'] = element.text
                    elif element.tag == 'fingerprint':
                        archive['fingerprint'] = (element.text == 'true')
                    elif element.tag == 'onlyIfSuccessful':
                        # only-if-success first available in JJB 1.3.0
                        archive['only-if-success'] = (element.text == 'true')
                    elif element.tag == 'defaultExcludes':
                        # default-excludes is not yet available in JJB master
                        archive['default-excludes'] = (element.text == 'true')
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "XML %s" % element.tag)

                publishers.append({'archive': archive})

            elif child.tag == 'hudson.plugins.descriptionsetter.DescriptionSetterPublisher':  # NOQA
                setter = OrderedDict()
                for element in child:
                    if element.tag == 'regexp':
                        setter['regexp'] = element.text
                    elif element.tag == 'regexpForFailed':
                        setter['regexp-for-failed'] = element.text
                    elif element.tag == 'setForMatrix':
                        setter['set-for-matrix'] = (element.text == 'true')
                    elif element.tag == 'description':
                        setter['description'] = element.text
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "XML %s" % element.tag)

                publishers.append({'description-setter': setter})

            elif child.tag == 'hudson.tasks.Fingerprinter':
                fingerprint = OrderedDict()
                for element in child:
                    if element.tag == 'targets':
                        fingerprint['files'] = element.text
                    elif element.tag == 'recordBuildArtifacts':
                        fingerprint['record-artifacts'] = (element.text == 'true')
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "XML %s" % element.tag)
                publishers.append({'fingerprint': fingerprint})

            elif child.tag == 'hudson.plugins.emailext.ExtendedEmailPublisher':
                ext_email = OrderedDict()
                for element in child:
                    if element.tag == 'recipientList':
                        if element.text != '$DEFAULT_RECIPIENTS':
                            ext_email['recipients'] = element.text

                    elif element.tag == 'replyTo':
                        if element.text != '$DEFAULT_REPLYTO':
                            ext_email['reply-to'] = element.text

                    elif element.tag == 'contentType':
                        if element.text != 'default':
                            mime_content_type = {
                                'text/plain': 'text',
                                'text/html': 'html',
                                'both': 'both-html-text',
                            }
                            ctype = element.text
                            if ctype not in mime_content_type:
                                raise NotImplementedError('cannot handle email-ext contentType "%s"' % ctype)
                            ext_email['content-type'] = mime_content_type[ctype]

                    elif element.tag == 'defaultSubject':
                        if element.text != '$DEFAULT_SUBJECT':
                            ext_email['subject'] = element.text

                    elif element.tag == 'defaultContent':
                        if element.text != '$DEFAULT_CONTENT':
                            ext_email['body'] = element.text

                    elif element.tag == 'attachBuildLog':
                        if element.text == 'true':
                            ext_email['attach-build-log'] = True

                    # TODO not actually supported in JJB yet
                    elif element.tag == 'compressBuildLog':
                        if element.text == 'true':
                            ext_email['compress-build-log'] = True

                    elif element.tag == 'attachmentsPattern':
                        if element.text:
                            ext_email['attachments'] = element.text

                    elif element.tag == 'saveOutput':
                        if element.text == 'true':
                            ext_email['save-output'] = True

                    elif element.tag == 'disabled':
                        if element.text == 'true':
                            ext_email['disable-publisher'] = True

                    elif element.tag == 'presendScript':
                        if element.text != '$DEFAULT_PRESEND_SCRIPT':
                            ext_email['presend-script'] = element.text

                    elif element.tag == 'configuredTriggers':
                        # JJB defaults "failure" to true
                        ext_email['failure'] = False
                        for trigger in element:
                            # TODO check that triggers have their default
                            # config, as JJB does not handle anything else.
                            triggerClass = re.sub(r'^hudson\.plugins\.emailext\.plugins\.trigger\.', '', trigger.tag)
                            if triggerClass == 'AlwaysTrigger':
                                ext_email['always'] = True
                            elif triggerClass == 'UnstableTrigger':
                                ext_email['unstable'] = True
                            elif triggerClass == 'FirstFailureTrigger':
                                ext_email['first-failure'] = True
                            elif triggerClass == 'NotBuiltTrigger':
                                ext_email['not-built'] = True
                            elif triggerClass == 'AbortedTrigger':
                                ext_email['aborted'] = True
                            elif triggerClass == 'RegressionTrigger':
                                ext_email['regression'] = True
                            elif triggerClass == 'FailureTrigger':
                                ext_email['failure'] = True
                            elif triggerClass == 'SecondFailureTrigger':
                                ext_email['second-failure'] = True
                            elif triggerClass == 'ImprovementTrigger':
                                ext_email['improvement'] = True
                            elif triggerClass == 'StillFailingTrigger':
                                ext_email['still-failing'] = True
                            elif triggerClass == 'SuccessTrigger':
                                ext_email['success'] = True
                            elif triggerClass == 'FixedTrigger':
                                ext_email['fixed'] = True
                            elif triggerClass == 'StillUnstableTrigger':
                                ext_email['still-unstable'] = True
                            elif triggerClass == 'PreBuildTrigger':
                                ext_email['pre-build'] = True
                            else:
                                raise NotImplementedError("cannot handle email-ext trigger %s" % trigger.tag)
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "XML %s" % element.tag)

                publishers.append({'email-ext': ext_email})

            elif child.tag == 'hudson.tasks.junit.JUnitResultArchiver':
                junit_publisher = OrderedDict()
                for element in child:
                    if element.tag == 'testResults':
                        junit_publisher['results'] = element.text
                    elif element.tag == 'keepLongStdio':
                        junit_publisher['keep-long-stdio'] = \
                            (element.text == 'true')
                    elif element.tag == 'healthScaleFactor':
                        junit_publisher['health-scale-factor'] = element.text
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "XML %s" % element.tag)
                publishers.append({'junit': junit_publisher})

            elif child.tag == 'hudson.plugins.parameterizedtrigger.BuildTrigger':
                build_trigger = OrderedDict()

                for element in child:
                    for sub in element:
                        if sub.tag == 'hudson.plugins.parameterizedtrigger.BuildTriggerConfig':     # NOQA
                            for config in sub:
                                if config.tag == 'projects':
                                    build_trigger['project'] = config.text
                                elif config.tag == 'condition':
                                    build_trigger['condition'] = config.text
                                elif config.tag == 'triggerWithNoParameters':
                                    build_trigger['trigger-with-no-params'] = \
                                        (config.text == 'true')
                                elif config.tag == 'configs':
                                    pass
                                else:
                                    raise NotImplementedError("cannot handle "
                                                              "XML %s" % config.tag)

                publishers.append({'trigger-parameterized-builds': build_trigger})

            elif child.tag == 'hudson.tasks.Mailer':
                email_settings = OrderedDict()
                for element in child:

                    if element.tag == 'recipients':
                        email_settings['recipients'] = element.text
                    elif element.tag == 'dontNotifyEveryUnstableBuild':
                        email_settings['notify-every-unstable-build'] = \
                            (element.text == 'true')
                    elif element.tag == 'sendToIndividuals':
                        email_settings['send-to-individuals'] = \
                            (element.text == 'true')
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "email %s" % element.tag)
                publishers.append({'email': email_settings})

            elif child.tag == 'htmlpublisher.HtmlPublisher':
                if len(child) != 1 or len(child[0]) != 1 \
                        or child[0].tag != 'reportTargets' \
                        or child[0][0].tag != 'htmlpublisher.HtmlPublisherTarget':
                    raise NotImplementedError("can only handle a single HtmlPublisherTarget")

                html_settings = OrderedDict()

                for element in child[0][0]:

                    if element.tag == 'reportName':
                        html_settings['name'] = element.text
                    elif element.tag == 'reportDir':
                        html_settings['dir'] = element.text
                    elif element.tag == 'reportFiles':
                        html_settings['files'] = element.text
                    elif element.tag == 'alwaysLinkToLastBuild':
                        html_settings['link-to-last-build'] = element.text == 'true'
                    elif element.tag == 'keepAll':
                        html_settings['keep-all'] = element.text == 'true'
                    elif element.tag == 'allowMissing':
                        html_settings['allow-missing'] = element.text == 'true'
                    elif element.tag == 'wrapperName' and \
                            element.text == 'htmlpublisher-wrapper.html':
                        pass
                    else:
                        raise NotImplementedError("cannot handle "
                                                  "html setting %s" % element.tag)
                publishers.append({'html-publisher': html_settings})
            elif child.tag == 'hudson.plugins.cobertura.CoberturaPublisher':
                cobertura = OrderedDict()
                targets = {'healthyTarget': 'healthy',
                           'unhealthyTarget': 'unhealthy',
                           'failingTarget': 'failing'}
                targetList = {}
                for param in child:
                    if param.tag == 'coberturaReportFile':
                        cobertura['report-file'] = param.text
                    elif param.tag == 'onlyStable':
                        cobertura['only-stable'] = param.text == 'true'
                    elif param.tag == 'failUnhealthy':
                        cobertura['fail-unhealthy'] = param.text == 'true'
                    elif param.tag == 'failUnstable':
                        cobertura['fail-unstable'] = param.text == 'true'
                    elif param.tag == 'autoUpdateHealth':
                        cobertura['health-auto-update'] = param.text == 'true'
                    elif param.tag == 'autoUpdateStability':
                        cobertura['stability-auto-update'] = param.text == 'true'
                    elif param.tag == 'zoomCoverageChart':
                        cobertura['zoom-coverage-chart'] = param.text == 'true'
                    elif param.tag == 'failNoReports':
                        cobertura['fail-no-report'] = param.text == 'true'
                    elif param.tag == 'sourceEncoding':
                        cobertura['source-encoding'] = param.text
                    elif param.tag in targets.keys():
                        if 'targets' not in cobertura:
                            cobertura['targets'] = []
                        try:
                            for te in param.findall('targets/entry'):
                                metric = te.find('hudson.plugins.cobertura.targets.CoverageMetric')
                                number = te.find('int')
                                if metric.text.lower() not in targetList.keys():
                                    targetList[metric.text.lower()] = {}
                                targetList[metric.text.lower()] = dict_merge(targetList[metric.text.lower()],  {targets[param.tag]: int(number.text)})
                        except KeyError, e:
                            print("cannot handle XML %s" % param.tag)
                            raise e
                for tl, tldef in targetList.items():
                    cobertura['targets'].append({tl: tldef})
                publishers.append({'cobertura': cobertura})

            elif child.tag == 'jenkins.plugins.slack.SlackNotifier':
                # Do nothing, it's all handled in the SlackJobProperty
                pass

            else:
                raise NotImplementedError("cannot handle XML %s" % child.tag)

        except NotImplementedError, e:
            print "going raw because: %s" % e
            insert_rawxml(child, publishers)

    return [['publishers', publishers]]


def handle_buildwrappers(top):
    wrappers = []

    for child in top:
        wrappers.append(handle_buildwrapper(child))

    return [['wrappers', wrappers]]


def handle_buildwrapper(wrapper):
    try:
        if wrapper.tag == 'EnvInjectPasswordWrapper':
            inject = OrderedDict()
            for element in wrapper:
                if element.tag == 'injectGlobalPasswords':
                    inject['global'] = (element.text == 'true')
                elif element.tag == 'maskPasswordParameters':
                    inject['mask-password-params'] = (element.text == 'true')
                elif element.tag == 'passwordEntries':
                    if len(list(element)) > 0:
                        raise NotImplementedError('TODO: implement handling '
                                                  'here')
                else:
                    raise NotImplementedError("cannot handle "
                                              "XML %s" % element.tag)
            return {'inject': inject}

        elif wrapper.tag == 'hudson.plugins.build__timeout.BuildTimeoutWrapper':
            timeout = OrderedDict()
            for element in wrapper:
                if element.tag == 'strategy':
                    if element.attrib['class'] == 'hudson.plugins.build_timeout.impl.AbsoluteTimeOutStrategy':
                        timeout['type'] = 'absolute'
                        timeout['timeout'] = int(element.findtext('timeoutMinutes'))

                    else:
                        raise NotImplementedError("cannot handle BuildTimeoutWrapper strategy %s" % element.attrib['class'])

                elif element.tag == 'operationList':
                    for operation in element:
                        if operation.tag == 'hudson.plugins.build__timeout.operations.FailOperation':
                            timeout['fail'] = True

                        else:
                            raise NotImplementedError("cannot handle BuildTimeoutWrapper operation %s" % operation.tag)

                else:
                    raise NotImplementedError("cannot handle BuildTimeoutWrapper wrapper %s" % element.tag)

            return {'timeout': timeout}

        elif wrapper.tag == 'hudson.plugins.ansicolor.AnsiColorBuildWrapper':
            return {'ansicolor': {'colormap': 'xterm'}}

        elif wrapper.tag == 'com.cloudbees.jenkins.plugins.sshagent.SSHAgentBuildWrapper':    # NOQA
            ssh_agents = OrderedDict()
            for element in wrapper:
                if element.tag == 'credentialIds':
                    keys = []
                    for key in element:
                        keys.append(key.text)
                    ssh_agents['users'] = keys
                elif element.tag == 'ignoreMissing':
                    pass
                else:
                    raise NotImplementedError("cannot handle "
                                              "XML %s" % element.tag)

            return {'ssh-agent-credentials': ssh_agents}

        elif wrapper.tag == 'org.jenkinsci.plugins.buildnamesetter.BuildNameSetter':  # NOQA
            return {'build-name': {'name': wrapper[0].text}}

        else:
            raise NotImplementedError("cannot handle XML %s" % wrapper.tag)

    except NotImplementedError, e:
        print "going raw because: %s" % e
        return create_rawxml(wrapper)


def handle_executionstrategy(top):
    strategy = OrderedDict()
    for child in top:

        if child.tag == 'runSequentially':
            strategy['run-sequentially'] = (child.text == 'true')
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    return [['execution-strategy', strategy]]


# Handle "<logrotator>...</logrotator>"'
def handle_logrotator(top):
    logrotate = OrderedDict()
    for child in top:

        if child.tag == 'daysToKeep':
            logrotate['daysToKeep'] = child.text
        elif child.tag == 'numToKeep':
            logrotate['numToKeep'] = child.text
        elif child.tag == 'artifactDaysToKeep':
            logrotate['artifactDaysToKeep'] = child.text
        elif child.tag == 'artifactNumToKeep':
            logrotate['artifactNumToKeep'] = child.text
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    return [['logrotate', logrotate]]


# Handle "<combinationFilter>a != &quot;b&quot;</combinationFilter>"
def handle_combinationfilter(top):
    return [['combination-filter', top.text]]


# Handle "<assignedNode>server.example.com</assignedNode>"
def handle_assignednode(top):
    return [['node', top.text]]


# Handle "<displayName>my cool job</displayName>"
def handle_displayname(top):
    return [['display-name', top.text]]


# Handle "<quietPeriod>5</quietPeriod>"
def handle_quietperiod(top):
    return [['quiet-period', top.text]]


# Handle "<scmCheckoutRetryCount>8</scmCheckoutRetryCount>"
def handle_scmcheckoutretrycount(top):
    return [['retry-count', top.text]]


def handle_customworkspace(top):
    return [['workspace', top.text]]


def insert_rawxml(node, output):
    output.append(create_rawxml(node))


def create_rawxml(node):
    import xml.etree.ElementTree as ET
    xml = ET.tostring(node).strip() + '\n'
    return {'raw': {'xml': xml}}
