Ext.define('DocumentTools.store.Tags', {
    extend: 'Ext.data.Store',
    
    model: 'DocumentTools.model.Tag',
	proxy: {
		type: 'ajax',
		url: '../reebill/dlatags',
	    pageParam: false, 
    	startParam: false,
    	limitParam: false,
		reader: {
			type: 'json',
			root: 'tags'
		}
	}
});