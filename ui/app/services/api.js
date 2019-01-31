import AjaxService from 'ember-ajax/services/ajax';
import ENV from 'zeus/config/environment';
import { Promise, hash } from 'rsvp';
import { set } from '@ember/object';
import { typeOf } from '@ember/utils';
import { updateObject } from 'apimas-docs/utils';


export default class ApiService extends AjaxService {
  host = ENV.APP.apiHost;
  trusteesMap = {};

  normalizeStage(id, stage, model, overview) {
    let document = this.pathsToDoc(stage.document || {});
    let options = stage.options || {};
    let label = stage.label || stage.status;
    let consensus_id = stage.consensus_id;
    let meta = {};
    let path = '/' + id;
    let paths = this.prefixedPaths(path, stage.document || {});
    let positions = stage.positions ? this.prefixedPaths(path, stage.positions) : null;

    let docPaths = this.prefixedPaths(path, stage.document);
    let prefixedOptions = this.prefixedPaths(path, options);
    let analysis = this.prefixedPaths(path, stage.analysis);

    if (!this.trusteesMap[stage.peer_id]) {
      this.trusteesMap[stage.peer_id] = stage.peer_id;
    }

    if (stage.document && stage.document.hasOwnProperty('trustees')) {
      Object.keys(stage.document).forEach((key) => {
        if (!key.startsWith('trustees/')) { return }
        let name = key.split("/").slice(-1)[0];
        this.trusteesMap[stage.document[key]] = name;
      });
    }

    if (stage.peer_id) {
      stage.peer = this.trusteesMap[stage.peer_id];
    }

    function disableIfJoined(peer_key, key, actionPath, meta) {
      if (key.startsWith(actionPath + '/')) {
        let name = key.split("/").slice(-1)[0];
        if (name == peer_key) {
          meta[actionPath].action_disabled = true;
        }
      }
    }

    function rootOptions(key, options) {
      let root = key.split('/').slice(0, -1).join('/') + '/*';
      // if (options[root]) { debugger; }
      return options[root] || {};
    }

    Object.keys(paths).forEach((key) => {
      let keyMeta = meta[key] = meta[key] || {};
      Object.assign(meta[key], prefixedOptions[key] || {});
      Object.assign(meta[key], rootOptions(key, prefixedOptions));


      // zeus specific
      if (key.startsWith('/stage_A_1/trustees/')) {
        if (paths[key] == stage.peer_id) {
          meta['/stage_A_1/trustees'].action_disabled = true;
        }
      }

      disableIfJoined(stage.peer, key, '/stage_B_1/public_shares', meta);
      disableIfJoined(stage.peer, key, '/stage_C_1/mixers', meta);

      keyMeta.lock_action = false;
      if (keyMeta.type && keyMeta.type == 'dict') {
        if (docPaths[key] !== null) {
          keyMeta.dict_locked = true;
          keyMeta.dict_locked_value = docPaths[key];
        }
        keyMeta.lock_action = true;
      }
    });

    if (!stage.analysis && label && ['NO_TRANSITION', 'DONE'].includes(label.toUpperCase())) {
      Object.keys(docPaths).forEach((key) => {
        meta[key] = meta[key] || {}
        meta[key].state_label = label.toLowerCase();
      })
    }

    if (stage.our_node_analysis) {
      Object.keys(analysis).forEach((path) => {
        meta[path].analysis = meta[path].analysis || {};
      });
    }

    if (stage.labels) {
      let prefixedLabels = this.prefixedPaths(path, stage.labels);
      Object.keys(prefixedLabels).forEach((key) => {
        meta[key] = meta[key] || {};
        meta[key].state_label = prefixedLabels[key].toLowerCase();
      });
    }

    if (positions) {
      let localPeers = Object.assign({}, this.trusteesMap);
      localPeers[stage.peer_id] = 'us';
      Object.keys(positions).forEach((path) => {
        let keyPositions = positions[path];
        if (!keyPositions) { return; }
        let pathMeta = meta[path];
        if (!pathMeta) { return; }

        let key = path.split("/").slice(2).join("/");
        let aprioriData = {};
        let data = {};
        if (stage.apriori_positions[key]) {
          stage.apriori_positions[key].forEach((item) => {
            let [value, proposer, peers] = item;
            let proposerName = localPeers[proposer];
            aprioriData[proposerName] = { value: value, proposed: true, consented: false }
            peers.forEach((p) => {
              let name = localPeers[p];
              aprioriData[name] = aprioriData[name] || {}
              aprioriData[name].value = value;
              aprioriData[name].consented = true;
            })
          });
        }
        //let docValue = stage.document[key];

        pathMeta.positions = positions[path];
        let inConflict = keyPositions.length > 1;
        keyPositions.forEach((item) => {
          let [value, proposer, peers] = item;
          let proposerName = localPeers[proposer];
          let apriori = aprioriData[proposerName] || {};
          data[proposerName] = {
            value: value,
            consented: false,
            proposed: true,
            apriori: apriori,
            proposing: !apriori.proposed,
            conflict: inConflict && ((value != apriori.value) && !apriori.proposed)
          }
          peers.forEach((p) => {
            p = localPeers[p];
            let apriori = aprioriData[p] || {};
            data[p] = data[p] || {};
            data[p].consented = true;
            data[p].value = value;
            data[p].conflict = inConflict && (value != apriori.value);
            data[p].apriori = apriori;
            data[p].consenting = !apriori.consented;
          });
        });

        let sorted = {};
        let keys = Object.keys(data).sort(function(a, b) { if (a == "us") { return -1000 } return a.length - b.length});
        keys.forEach((key) => {
          sorted[key] = data[key];
        });
        pathMeta.positions = sorted;
        if (model.meta[path]) {
          set(model.meta[path], 'positions', sorted);
        }
      });
    }

    let _stage = {};
    _stage.id = id;
    _stage.consensus_id = consensus_id;
    _stage.document = document;
    _stage.meta = meta;
    _stage.analysis = analysis;
    _stage.path = model.path;
    _stage.completed = stage.completed;
    _stage.running = model.running;
    _stage.pending = model.pending;
    _stage.instance = stage.instance;

    if (overview) {
      overview = this._normalizeOverview(overview);
      this.updateStageStateFromOverview(id, _stage, stage, overview);
    }
    return _stage;
  }

  getStage(user, neg_id, stage, model, force_overview) {
    let path = model.urlPath;
    if (model.completed &&!force_overview) { return Promise.resolve(model); }
    if (model.pending && !force_overview) { return Promise.resolve(model); }
    if (stage[0] == '/') { stage = stage.slice(1); }

    let prevPath = model.urlPath;
    let prevCompleted = model.completed;
    return this.request(`/${user}/stages/${path}/`).then((data) => {
      if (force_overview || (data.consensus_id && data.completed == false)) {
        return this.request(`/${user}/stages/`).then((overview) => {
          let normalized = this.normalizeStage(model.id, data, model, overview);
          if (normalized.urlPath != model.urlPath) {
            set(model, 'urlPath', normalized.urlPath);
            return this.getStage(user, neg_id, stage, model);
          } else {
            return this.updateFromResponse(model, data, overview);
          }
        });
      } else {
        return this.updateFromResponse(model, data);
      }
    });
  }

  updateFromResponse(model, data, overview) {
    let normalized = this.normalizeStage(model.id, data, model, overview);
    updateObject(model || {}, normalized, false);
    return model;
  }

  _normalizeOverview(overview) {
    let data = {};
    data.reports = {};
    (overview.reports || []).forEach((item) => {
      let _reports = data.reports[item.stage] = data.reports[item.stage] || [];
      _reports.push(item);
    });
    data.global_negotiation_id = overview.global_negotiation_id;
    data.next_instance = overview.next_instance;
    data.next_stage = overview.next_stage;
    return data;
  }

  updateStageStateFromOverview(key, model, rawStage, overview) {
    let instance, completed, pending, running, path, instanceId;
    let reports = overview.reports[key] || [];
    let lastReport = reports.slice(-1)[0] || null;

    if (lastReport == null) {
      if (rawStage && rawStage.hasOwnProperty('instance')) {
        instance = rawStage.instance;
      } else {
        instance = model.instance || 1;
      }
      if (rawStage && rawStage.hasOwnProperty('completed')) {
        completed = rawStage.completed;
      } else {
        completed = model.completed || false;
      }
    } else {
      if (lastReport.completed) {
        instance = lastReport.instance;
        completed = true;
      } else {
        instance = lastReport.instance + 1;
        completed = false
      }
    }
    path = key + '_' + instance;

    instanceId = key + '_' + instance;
    let nextStage = overview.next_stage + '_' + overview.next_instance;
    running = nextStage == instanceId;
    pending = !completed && !running;

    set(model, 'instance', instance);
    set(model, 'urlPath', path);
    set(model, 'path', '/' + key);
    set(model, 'completed', completed);
    set(model, 'running', running)
    set(model, 'instanceId', instanceId)
    set(model, 'pending', pending);
  }

  initStages(user, _stages/* neg_id */) {
    return this.request(`/${user}/stages/`).then((data) => {
      let stages = _stages || {};

      //var lastStage = null;
      Object.keys(data.meta).forEach((key) => {
        let stageData = data.meta[key];
        let stage = { id: key, document: {}, analysis: {}, consensus: {} };
        let overview = this._normalizeOverview(data);
        this.updateStageStateFromOverview(key, stage, stageData, overview);
        let stageReports = overview.reports[key]
        let lastReport = (stageReports && stageReports.slice(-1)[0]) || null;

        stage.id = key;
        stage.meta = { [stage.path]: {} };
        stage.global_negotiation = data.global_negotiation_id;
        stage.negotiation = stageData.stage_negotiation_id;
        stage.meta[stage.path] = {
          id: stageData.id,
          title: stageData.title,
          description: stageData.description,
          consensus: stageData.consensus
        }
        if (lastReport && lastReport.completed) {
          this.updateFromResponse(stage, lastReport, data);
        }
        stages[stage.id] = stage;
        //lastStage = stage;
      });
      return stages;
    }).then((stages) => {
        let promises = {};
        //let stop = {};
        Object.keys(stages).forEach((key) => {
          let stage = stages[key];
          if (stage.pending) {
            promises[key] = Promise.resolve(stage);
          } else {
            promises[key] = this.getStage(user, this.negId, stages[key].path, stages[key]);
          }
        });
        return hash(promises).then((_stages) => {
          let resp = {};
          Object.keys(stages).forEach((k) => {
            resp[k] = _stages[k];
          });
          return resp;
        });
    });
  }


  prefixedPaths(root, data) {
    let opts = {}
    Object.keys(data || {}).forEach((key) => {
      let keyOpts = data[key];
      let path = [root, key].join('/')
      if (key == "") { path = root; }
      opts[path] = keyOpts;
    });
    return opts;
  }

  pathsToDoc(doc) {
    let data = {};
    if (!doc) { return {} }
    Object.keys(doc).forEach((key) => {
      let target = data;
      let parts = key.split('/').slice(0, -1);
      let parentTarget = null;
      let lastPart = null;
      parts.forEach((part) => {
        if (part == "") { return }
        if (!target[part]) {
          target[part] = {}
        }
        parentTarget = target;
        lastPart = part;
        target = target[part];
      });
      if (key == "") { return }

      if (typeOf(target) != "object") {
        let val = target;
        target = parentTarget[lastPart] = {};
        Object.defineProperty(target, '__value', { value: val, enumerable: false });
      }

      set(target, key.split('/').slice(-1)[0], doc[key]);
    });
    return data;
  }

  contribute(user, stage, model) {
    let path = model.urlPath;
    let url = `/${user}/stages/${path}/contribute/`;
    return this.post(url).then((data) => {
      return this.request(`/${user}/stages/`).then((overview) => {
        this.updateFromResponse(model, data, overview);
      })
    });
  }

  updateStages(model, user, neg_id, force_overview) {
    let promises = {};
    let models = [];
    Object.keys(model).forEach((key) => { models.push(model[key]); })
    let triggerOverview = false;
    models.forEach((stage, i) => {
      promises[stage.id] = this.getStage(user, neg_id, stage.id, stage, force_overview).then((model) => {
        if (model.completed) {
          let next = models[i + 1];
          if (next && !next.running && !next.completed) { triggerOverview = next; }
        }
        return model;
      });
    })
    return hash(promises).then((stages) => {
      if (triggerOverview) {
        return this.getStage(user, neg_id, triggerOverview.id, triggerOverview, true).then((s) => {
          stages[s.id] = s;
          return stages;
        })
      } else {
        return stages;
      }
    });
  }

  getParamValue(context, meta, key, value) {
    if (meta.type == "dict" && value == "CLOSE") {
      return "lock";
    }
    if (meta.action == "choices") {
      if (meta.type == "int") {
        return value ? parseInt(value) : null;
      }
      return value || null;
    }
    if (meta.action && meta.action.startsWith("compute")) {
      let inst = {}
      if (meta.params) {
        meta.params.forEach((param) => {
          if (context[param]) {
            inst[param] = context[param];
          }
        });
      }
      return inst;
    }
    if (meta.type && meta.type == "int") {
      return value ? parseInt(value) : null;
    }
    return value;
  }

  _setsValue(meta) { return !meta.action || !meta.action.startsWith('compute'); }

  updatePath(user, stage, key, value, meta, model) {
    let path = model.urlPath;
    let url = `/${user}/stages/${path}/update/`;
    let params = this.getParamValue(model.document, meta, key, value);
    let data = { instructions: { [key]: params } }
    let dotKey = key.split('/').join('.');
    set(meta, 'updating', true);
    if (this._setsValue(meta)) {
      set(model.document, dotKey, params);
    }
    return this.post(url, { data, contentType: 'application/json' }).then((data) => {
      this.updateFromResponse(model, data);
    }).finally(() => {
      set(meta, 'updating', false);
    });
  }
}
