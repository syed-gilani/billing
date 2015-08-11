'use strict';

angular.module('createExtractor').

// add service for getting data from server/DB
factory('DBService', ['$http',
  function($http){
    var DBService = {};

    // Each of these functions return a promise that executes the request.

    // Given an id, returns the bill's id , utility_id, and pdf url on success
    DBService.getUtilBill = function(id){
      return $http.get('/utilitybills/utilitybills/'+id);
    };

    //Returns a list of the applier keys currently available to use in extraction. 
    DBService.getApplierKeys = function(){
      return $http.get('/applier-keys');
    };

    // Returns a list of possible field types as a string array
    DBService.getFieldTypes = function(){
      return $http.get('/get-field-types');
    };

    // Returns a list of possible data types for a field as a string array
    DBService.getDataTypes = function(){
      return $http.get('/field-data-types');
    };

    // Returns a list of the id's and names of available LayoutExtractors in the DB
    DBService.getExtractors = function(){
      return $http.get('/extractors');
    };

    // Saves the current extractor to the DB. If the extractor has an ID 
    // (i.e. it already exists in the DB), then the ID is sent so that 
    // the DB can udpate the existing extractor instead of creating a new one.
    // Otherwise, the DB will create a new extractor with a new ID. 
    // The ID of the extractor is returned. 
    DBService.saveExtractor = function(extractor){
      if (extractor.extractor_id){
        return $http.put('/extractors/'+extractor.extractor_id, {extractor:extractor});
      } else {
        return $http.post('/extractors', {extractor:extractor});
      }
    };

    // Loads an extractor by ID from the database.
    DBService.loadExtractor = function(id){
      return $http.get('/extractors/' + id);
    };

    // For a given bill, returns the first object that matches 'regex'. 
    // min_page and max_page can be used to narrow down which pages are searched.
    DBService.getTextLine = function(bill_id, regex, min_page, max_page){
      var min_page_str = (min_page == null) ? "" : "/"+min_page;
      var max_page_str = (max_page == null) ? "" : "/"+max_page;
      return $http.post('/get-text-lines-page/'+bill_id+min_page_str+max_page_str, {regex: regex});
    };

    // get all the layout elements for a bill.
    // Currently only gets text lines, not text boxes or images, etc. 
    DBService.getLayoutElements = function(bill_id){
      return $http.get('/utilitybills/'+bill_id+'/layout-elements/textline');
    };

    // Tests a field on a given bill, and returns the output (after the type conversion function has been applier)
    DBService.previewField = function(bill_id, field){
      return $http.post('/preview-field/'+bill_id, field);
    };

    // Gets a list of utilities from the database
    DBService.getUtilities = function(){
      return $http.get('/utilitybills/utilities');
    }

    /* For running tests */

    // get a list of currently running batch tests on the server.
    DBService.getRunningBatchTests = function(){
      return $http.get('/get-running-tests');
    }

    // Run a batch test on the server. 
    // Returns the task_id of the job, and the number of bills to be run.
    DBService.runBatchTest = function(test){
      return $http.post('/run-batch-test', test);
    }

    // Runs a test on one bill
    DBService.runIndividualTest = function(test){
      return $http.post('/run-indiv-test', test);
    }

    // Gets status for a running batch job
    DBService.getTestStatus = function(task_id){
      return $http.get('/test-status/'+task_id);
    }

    // Stops a running batch job
    DBService.stopTest = function(task_id){
      return $http.get('/stop-task/'+task_id);
    }

    return DBService;
}]);