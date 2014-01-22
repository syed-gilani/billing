Ext.define('DocumentTools.controller.Regions',{extend:'Ext.app.Controller',views:['Regions'],stores:['Regions'],refs:[{ref:'newRegionWindow',selector:'window[name=newRegionWindow]'},{ref:'regionsGrid',selector:'grid[id=regionsGrid]'},{ref:'colorField',selector:'colorfield[name=color]'},{ref:'regionsGrid',selector:'grid[id=regionsGrid]'},{ref:'newRegionForm',selector:'form[id=newRegionForm]'},{ref:'sliderField',selector:'sliderfield[name=opacity]'},{ref:'viewerComponent',selector:'[id=viewerComponent]'}],init:function(){this.application.on({scope:this});this.control({'grid[id=regionsGrid]':{cellclick:function(){}},'button[action=addRegion]':{click:this.addRegion},'button[action=deleteRegion]':{click:this.deleteRegion},'button[action=saveNewRegion]':{click:this.saveNewRegion},'button[action=cancelNewRegion]':{click:function(){this.getNewRegionWindow().close()}},'button[action=zoomIn]':{click:this.zoomIn},'button[action=zoomOut]':{click:this.zoomOut},'viewport':{afterrender:function(){var scope=this;window.setTimeout(function(){scope.initViewer.apply(scope,arguments)},2000)}},'sliderfield[name=opacity]':{change:this.handleOpacityChange}});this.getRegionsStore().on({datachanged:this.markRegions,scope:this})},initViewer:function(){var componentWidth=this.getViewerComponent().getWidth();var componentHeight=this.getViewerComponent().getHeight();this.imageWidth=$('#documentImage').width();this.imageHeight=$('#documentImage').height();this.currentZoom=componentWidth/this.imageWidth;if((this.currentZoom*this.imageHeight)>componentHeight)this.currentZoom=componentHeight/this.imageHeight;this.originalWidth=this.currentZoom*this.imageWidth;this.originalHeight=this.currentZoom*this.imageHeight;$('#documentImage').width(this.originalWidth);$('#documentImage').height(this.originalHeight);this.markRegions();this.getViewerComponent().on({resize:this.handleResize,scope:this})},handleResize:function(){var componentWidth=this.getViewerComponent().getWidth();var componentHeight=this.getViewerComponent().getHeight();this.currentZoom=componentWidth/this.imageWidth;if((this.currentZoom*this.imageHeight)>componentHeight)this.currentZoom=componentHeight/this.imageHeight;this.originalWidth=this.currentZoom*this.imageWidth;this.originalHeight=this.currentZoom*this.imageHeight;$('#documentImage').width(this.originalWidth);$('#documentImage').height(this.originalHeight);this.markRegions()},addRegion:function(){this.getNewRegionWindow().show();this.handleOpacityChange()},deleteRegion:function(){var selections=this.getRegionsGrid().getSelectionModel().getSelection();if(selections)this.getRegionsStore().remove(selections)},markRegions:function(){var scope=this;var store=this.getRegionsStore();var currentZoom=this.currentZoom;$('.region').remove();store.each(function(rec){var newRegion=$('<div class="region" title="'+(rec.get('description')||'')+'" id="region_'+rec.get('id')+'"><b>'+rec.get('name')+'</b></div>');$('#imageContainer').append(newRegion);var position=$('#imageContainer').position();$(newRegion).css('position','absolute').css('width',rec.get('width')*currentZoom).css('height',rec.get('height')*currentZoom).css('top',position.top+rec.get('y')*currentZoom).css('left',position.left+rec.get('x')*currentZoom).css('opacity',rec.get('opacity')).css('background-color','#'+rec.get('color')).draggable({containment:"parent",stop:function(){scope.updateLocation.apply(scope,arguments)}}).resizable({stop:function(){scope.updateSize.apply(scope,arguments)}})})},saveNewRegion:function(){var form=this.getNewRegionForm(),name=form.down('[name=name]').getValue(),description=form.down('[name=description]').getValue(),color=form.down('[name=color]').getValue(),opacity=form.down('[name=opacity]').getValue(),store=this.getRegionsStore();var newRegion=DocumentTools.model.Region.create({id:Ext.id(),name:name,description:description,color:color,opacity:opacity/100});store.add(newRegion);form.getForm().reset();this.getNewRegionWindow().close()},handleOpacityChange:function(){Ext.ux.ColorField.superclass.setFieldStyle.call(this.getColorField(),{'opacity':this.getSliderField().getValue()/100})},updateSize:function(event,ui){var domId=ui.helper.attr('id');var id=domId.substring(7);var rec=this.getRegionsStore().findRecord('id',id);if(!rec)return;rec.set('height',ui.size.height);rec.set('width',ui.size.width)},updateLocation:function(event,ui){var domId=ui.helper.attr('id');var id=domId.substring(7);var rec=this.getRegionsStore().findRecord('id',id);if(!rec)return;rec.set('y',ui.offset.top);rec.set('x',ui.offset.left)},zoomIn:function(){this.currentZoom=this.currentZoom+.15;this.zoom()},zoomOut:function(){this.currentZoom=this.currentZoom-.15;this.zoom()},zoom:function(){$('#documentImage').width(this.currentZoom*this.imageWidth);$('#documentImage').height(this.currentZoom*this.imageHeight);this.markRegions()}});