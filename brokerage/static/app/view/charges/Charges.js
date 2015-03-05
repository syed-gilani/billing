Ext.define('ReeBill.view.charges.Charges', {
    extend: 'Ext.grid.Panel',

    alias: 'widget.charges',
    store: 'Charges',
    preventHeader: true,

    height: 300,

    plugins: [{
        ptype: 'cellediting',
        clicksToEdit: 2
    }],

    features: [{
        ftype: 'summary'
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        itemId: 'chargesGridView',
        getRowClass: function(record) {
            if (record.get('error')){
                return 'charges-grid-error';
            }
        }
    },

    forceFit: true,
    
    columns: [{
        header: 'Name',
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 180
    },{
        header: 'Total',
        width: 110,
        sortable: true,
        dataIndex: 'target_total',
        editor: {
            xtype: 'numberfield',
            allowBlank: false,
            step: 0.01
        },
        summaryType: function(records){
            var sum = 0;
            Ext.Array.each(records, function(record){
                sum += record.get('target_total');
            });
            return sum;
        },
        align: 'right',
        renderer: Ext.util.Format.usMoney
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            text: 'Insert',
            action: 'newCharge',
            iconCls: 'silk-add'
        },{        
            xtype: 'button',
            text: 'Remove',
            action: 'removeCharge',
            iconCls: 'silk-delete',
            disabled: true
        }]
    }]
});
