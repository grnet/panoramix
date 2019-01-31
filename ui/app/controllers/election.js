import Controller from '@ember/controller';
import { action, computed } from '@ember-decorators/object';
import { service } from '@ember-decorators/service';
import { A } from '@ember/array';
import { typeOf } from '@ember/utils';
import { set, get } from '@ember/object';
import { task, timeout } from 'ember-concurrency';
import ENV from 'zeus/config/environment';


export default class ElectionController extends Controller {

  updateInProgress = false;

  init() {
    super.init(...arguments);
    this.manual = false;
    this.set('queryParams', ['manual']);
  }

  @service api;
  @service paperToaster;

  @computed('manual')
  get manualRefresh() {
    return this.manual
  }
  set manualRefresh(val) { return val; }

  appTitle = ENV.APP.title;
  appSubtitle = ENV.APP.subtitle;

  inProgress = true;
  updateInProgress = false;
  expandedPaths = [];

  handleApiError(err) {
    console.error(err);
    this.paperToaster.show("api error", {
      duration: 3000,
      toastClass: 'md-warn'
    });
    return null;
  }

  updateRunningPaths(paths) {
    let model = this.model;
    Object.keys(model).forEach((user) => {
      let _model = model[user];
      Object.keys(_model).forEach((key) => {
        if (_model[key].running) {
          paths.addObject(_model[key].path);
        }
      });
    });
    this.expandedPaths.setObjects(paths);
  }

  @action onKeyLock(user, stageId, item, value, evt) {
    this.onValueChange(user, stageId, item, "CLOSE", evt);
  }

  @action onValueChange(user, stageId, item, value, evt) {
    evt && evt.stopPropagation && evt.stopPropagation();

    console.log("UPDATE VALUE", item, value);
    let model = this.model[user];
    let path = item.path;
    let modelPath = [stageId, 'document'] .concat(item.path.split('/').slice(2)).join('.');
    let modelDotsPath = modelPath.split('/').join('.');
    let meta = model[stageId].meta[path];

    let update = this.get('updateModel').perform();
    let error = this.handleApiError.bind(this);

    let context = get(model, modelPath) || {};
    let key = path.split('/').slice(2).join('/')

    let promise = this.api.updatePath(user, stageId, key, value, meta, model[stageId]);
    this.set('updateInProgress', true);
    return promise.then(update).catch(error).finally(() => {
      this.set('updateInProgress', false);
    });
  }

  @action docAction(user, stage) {
    let error = this.handleApiError.bind(this);
    let update = this.get('updateModel');
    let model = this.model[user][stage];
    let completed = model.completed;
    this.api.contribute(user, stage, model).then((resp) => {
      update.perform().then((resp) => {
        if (model.completed != completed) {
          update.perform().then(() => {
            let paths = this.expandedPaths.concat();
            paths.removeObject(model.path);
            this.updateRunningPaths(paths);
          }).catch(() => { return true });
        } else {
          return resp;
        }
      }).catch(() => { return true });
    }).catch(error);
  }

  @action reloadModel() {
    this.get('updateModel').perform();
  }

  @action expandPath(path, state=null) {
    if (state != null) {
      if (state) {
        return this.expandPath(path);
      } else {
        return this.collapsePath(path);
      }
    }
    if (!this.expandedPaths.includes(path)) {
      this.expandedPaths.addObject(path);
    }
  }

  @action collapsePath(path) {
    if (this.expandedPaths.includes(path)) {
      this.expandedPaths.removeObject(path);
    }
  }

  @action showStatus(user, stage, path, label) {
    let meta = this.model[user][stage].meta[path];
    let data = {
      path: label || path,
      meta: this.model[user][stage].meta[path]
    };
    set(this, 'analysis', data);
    set(this, 'showDialog', true);
  }

  @action hideStatus(user, path) {
    set(this, 'analysis', null);
    set(this, 'showDialog', false);
  }

  onRefreshError = function() {
    debugger;
  }.on('refreshModels:errored')

  refreshModels = task(function * () {
    while (!this.manualRefresh) {
      yield timeout(ENV.APP.modelInterval || 5000);
      this.get('updateModel').perform().catch((err) => {
        console.log("refresh error", err);
      });
    }
  }).evented();

  updateModel = task(function * () {
    for (let user of this.users) {
      if (!this.model || !this.model[user]) { continue; }
      try {
        yield this.api.updateStages(this.model[user], user, this.negId);
      } catch(err) {
        this.handleApiError(err);
      }
    }
  }).drop();
}
